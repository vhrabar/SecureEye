#include <cerrno>
#include <csignal>
#include <cstdlib>

#include <arpa/inet.h>
#include <glob.h>
#include <libintl.h>
#include <pthread.h>
#include <stdexcept>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/signalfd.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <sys/syslog.h>
#include <sys/types.h>
#include <syslog.h>
#include <unistd.h>

#include <chrono>
#include <condition_variable>
#include <cstring>
#include <fstream>
#include <functional>
#include <future>
#include <mutex>
#include <regex>
#include <string>
#include <tuple>

#include <INIReader.h>

#include <security/pam_appl.h>
#include <security/pam_ext.h>
#include <security/pam_modules.h>

#include "enter_device.hh"
#include "main.hh"
#include "optional_task.hh"
#include <paths.hh>

const auto DEFAULT_TIMEOUT =
    std::chrono::duration<int, std::chrono::milliseconds::period>(100);
const auto MAX_RETRIES = 5;
constexpr std::size_t MAX_IPC_PAYLOAD = 4096;
constexpr int AUTHD_INTERNAL_ERROR = 99;

#define S(msg) gettext(msg)

auto json_escape(const std::string &value) -> std::string {
  std::string escaped;
  escaped.reserve(value.size());
  for (const auto ch : value) {
    if (ch == '"' || ch == '\\') {
      escaped.push_back('\\');
    }
    escaped.push_back(ch);
  }
  return escaped;
}

auto make_request_id() -> std::string {
  const auto now = std::chrono::steady_clock::now().time_since_epoch().count();
  return std::to_string(getpid()) + "-" + std::to_string(now);
}

auto get_pam_item_str(pam_handle_t *pamh, int item_type) -> std::string {
  const void *item = nullptr;
  if (pam_get_item(pamh, item_type, &item) != PAM_SUCCESS || item == nullptr) {
    return "";
  }

  return static_cast<const char *>(item);
}

auto get_remaining_timeout_ms(const std::chrono::steady_clock::time_point &deadline)
    -> int {
  const auto now = std::chrono::steady_clock::now();
  if (now >= deadline) {
    return 0;
  }

  return static_cast<int>(
      std::chrono::duration_cast<std::chrono::milliseconds>(deadline - now)
          .count());
}

auto wait_socket_event(int fd, short events,
                       const std::chrono::steady_clock::time_point &deadline)
    -> bool {
  while (true) {
    const auto timeout_ms = get_remaining_timeout_ms(deadline);
    if (timeout_ms <= 0) {
      return false;
    }

    struct pollfd pfd {
      .fd = fd,
      .events = events,
      .revents = 0,
    };

    const auto poll_res = poll(&pfd, 1, timeout_ms);
    if (poll_res == 0) {
      return false;
    }

    if (poll_res < 0) {
      if (errno == EINTR) {
        continue;
      }
      return false;
    }

    return (pfd.revents & events) != 0;
  }
}

auto connect_authd(const std::chrono::steady_clock::time_point &deadline) -> int {
  int fd = socket(AF_UNIX, SOCK_STREAM, 0);
  if (fd < 0) {
    return -1;
  }

  const auto flags = fcntl(fd, F_GETFL, 0);
  if (flags < 0 || fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) {
    close(fd);
    return -1;
  }

  struct sockaddr_un addr {};
  addr.sun_family = AF_UNIX;
  if (strlen(AUTHD_SOCKET_PATH) >= sizeof(addr.sun_path)) {
    close(fd);
    return -1;
  }
  strncpy(addr.sun_path, AUTHD_SOCKET_PATH, sizeof(addr.sun_path) - 1);

  const auto connect_res =
      connect(fd, reinterpret_cast<struct sockaddr *>(&addr), sizeof(addr));
  if (connect_res == 0) {
    return fd;
  }

  if (errno != EINPROGRESS) {
    close(fd);
    return -1;
  }

  if (!wait_socket_event(fd, POLLOUT, deadline)) {
    close(fd);
    return -1;
  }

  int so_error = 0;
  socklen_t so_error_len = sizeof(so_error);
  if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &so_error, &so_error_len) != 0 ||
      so_error != 0) {
    close(fd);
    return -1;
  }

  return fd;
}

auto send_all(int fd, const char *data, std::size_t len,
              const std::chrono::steady_clock::time_point &deadline) -> bool {
  std::size_t sent = 0;
  while (sent < len) {
    if (!wait_socket_event(fd, POLLOUT, deadline)) {
      return false;
    }

    const auto wrote = send(fd, data + sent, len - sent, 0);
    if (wrote < 0) {
      if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) {
        continue;
      }
      return false;
    }

    if (wrote == 0) {
      return false;
    }

    sent += static_cast<std::size_t>(wrote);
  }

  return true;
}

auto recv_exact(int fd, char *buffer, std::size_t len,
                const std::chrono::steady_clock::time_point &deadline) -> bool {
  std::size_t received = 0;
  while (received < len) {
    if (!wait_socket_event(fd, POLLIN, deadline)) {
      return false;
    }

    const auto read_bytes = recv(fd, buffer + received, len - received, 0);
    if (read_bytes < 0) {
      if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) {
        continue;
      }
      return false;
    }

    if (read_bytes == 0) {
      return false;
    }

    received += static_cast<std::size_t>(read_bytes);
  }

  return true;
}

auto read_authd_response_code(const std::string &payload,
                              const std::string &request_id,
                              int &result_code) -> bool {
  static const std::regex version_re("\"v\"\\s*:\\s*(\\d+)");
  static const std::regex type_re("\"type\"\\s*:\\s*\"([^\"]+)\"");
  static const std::regex request_id_re(
      "\"request_id\"\\s*:\\s*\"([^\"]*)\"");
  static const std::regex result_code_re(
      "\"result_code\"\\s*:\\s*(-?\\d+)");
  std::smatch match;

  if (!std::regex_search(payload, match, version_re) || match.size() < 2 ||
      std::stoi(match[1].str()) != AUTH_PROTOCOL_VERSION) {
    return false;
  }

  if (!std::regex_search(payload, match, type_re) || match.size() < 2 ||
      match[1].str() != "auth_response") {
    return false;
  }

  if (!std::regex_search(payload, match, request_id_re) || match.size() < 2 ||
      match[1].str() != request_id) {
    return false;
  }

  if (!std::regex_search(payload, match, result_code_re) || match.size() < 2) {
    return false;
  }

  result_code = std::stoi(match[1].str());
  switch (result_code) {
  case EXIT_SUCCESS:
  case CompareError::NO_FACE_MODEL:
  case CompareError::TIMEOUT_REACHED:
  case CompareError::ABORT:
  case CompareError::TOO_DARK:
  case CompareError::INVALID_DEVICE:
  case CompareError::RUBBERSTAMP:
  case AUTHD_INTERNAL_ERROR:
    return true;
  default:
    return false;
  }
}

auto authd_authenticate(pam_handle_t *pamh, const std::string &username) -> int {
  const auto deadline =
      std::chrono::steady_clock::now() + std::chrono::milliseconds(AUTH_TIMEOUT_MS);
  const auto request_id = make_request_id();
  const auto service = get_pam_item_str(pamh, PAM_SERVICE);
  const auto tty = get_pam_item_str(pamh, PAM_TTY);
  const auto rhost = get_pam_item_str(pamh, PAM_RHOST);
  const auto payload = "{\"v\":" + std::to_string(AUTH_PROTOCOL_VERSION) +
                       ",\"type\":\"auth_request\",\"request_id\":\"" +
                       json_escape(request_id) +
                       "\",\"username\":\"" + json_escape(username) +
                       "\",\"service\":\"" + json_escape(service) +
                       "\",\"tty\":\"" + json_escape(tty) +
                       "\",\"rhost\":\"" + json_escape(rhost) +
                       "\",\"deadline_ms\":" +
                       std::to_string(AUTH_TIMEOUT_MS) + "}";

  if (payload.size() > MAX_IPC_PAYLOAD) {
    return AUTHD_INTERNAL_ERROR;
  }

  const int fd = connect_authd(deadline);
  if (fd < 0) {
    return AUTHD_INTERNAL_ERROR;
  }

  const uint32_t frame_len = htonl(static_cast<uint32_t>(payload.size()));
  if (!send_all(fd, reinterpret_cast<const char *>(&frame_len), sizeof(frame_len),
                deadline) ||
      !send_all(fd, payload.c_str(), payload.size(), deadline)) {
    close(fd);
    return AUTHD_INTERNAL_ERROR;
  }

  uint32_t response_len_net = 0;
  if (!recv_exact(fd, reinterpret_cast<char *>(&response_len_net),
                  sizeof(response_len_net), deadline)) {
    close(fd);
    return AUTHD_INTERNAL_ERROR;
  }

  const auto response_len = ntohl(response_len_net);
  if (response_len == 0 || response_len > MAX_IPC_PAYLOAD) {
    close(fd);
    return AUTHD_INTERNAL_ERROR;
  }

  std::string response_payload(response_len, '\0');
  if (!recv_exact(fd, response_payload.data(), response_len, deadline)) {
    close(fd);
    return AUTHD_INTERNAL_ERROR;
  }
  close(fd);

  int result_code = AUTHD_INTERNAL_ERROR;
  if (!read_authd_response_code(response_payload, request_id, result_code)) {
    return AUTHD_INTERNAL_ERROR;
  }

  return result_code;
}

/**
 * Inspect the status code returned by authd.
 * @param  status        The result code
 * @param  conv_function The PAM conversation function
 * @return               A PAM return code
 */
auto secureEye_error(int status,
                 const std::function<int(int, const char *)> &conv_function)
    -> int {
  switch (status) {
  case CompareError::NO_FACE_MODEL:
    syslog(LOG_NOTICE, "Failure, no face model known");
    break;
  case CompareError::TIMEOUT_REACHED:
    conv_function(PAM_ERROR_MSG, S("Failure, timeout reached"));
    syslog(LOG_ERR, "Failure, timeout reached");
    break;
  case CompareError::ABORT:
    syslog(LOG_ERR, "Failure, general abort");
    break;
  case CompareError::TOO_DARK:
    conv_function(PAM_ERROR_MSG, S("Face detection image too dark"));
    syslog(LOG_ERR, "Failure, image too dark");
    break;
  case CompareError::INVALID_DEVICE:
    syslog(LOG_ERR, "Failure, not possible to open camera at configured path");
    break;
  case CompareError::RUBBERSTAMP:
    syslog(LOG_ERR, "Failure, rubberstamp verification failed");
    break;
  case AUTHD_INTERNAL_ERROR:
    syslog(LOG_ERR, "Failure, authd transport/protocol/internal error");
    break;
  default:
    syslog(LOG_ERR, "Failure, unknown error %d", status);
  }

  // As this function is only called for error status codes, signal an error to
  // PAM
  return PAM_AUTH_ERR;
}

/**
 * Format the success message if the status is successful or log the error in
 * the other case
 * @param  username      Username
 * @param  status        Status code
 * @param  config        INI  configuration
 * @param  conv_function PAM conversation function
 * @return          Returns the conversation function return code
 */
auto secureEye_status(char *username, int status, const INIReader &config,
                  const std::function<int(int, const char *)> &conv_function)
    -> int {
  if (status != EXIT_SUCCESS) {
    return secureEye_error(status, conv_function);
  }

  if (!config.GetBoolean("core", "no_confirmation", true)) {
    // Construct confirmation text from i18n string
    std::string confirm_text(S("Identified face as {}"));
    std::string identify_msg =
        confirm_text.replace(confirm_text.find("{}"), 2, std::string(username));
    conv_function(PAM_TEXT_INFO, identify_msg.c_str());
  }

  syslog(LOG_INFO, "Login approved");

  return PAM_SUCCESS;
}

/**
 * Check if SecureEye should be enabled according to the configuration and the
 * environment.
 * @param  config INI configuration
 * @param  username Username
 * @return        Returns PAM_AUTHINFO_UNAVAIL if it shouldn't be enabled,
 * PAM_SUCCESS otherwise
 */
auto check_enabled(const INIReader &config, const char *username) -> int {
  // Stop executing if SecureEye has been disabled in the config
  if (config.GetBoolean("core", "disabled", false)) {
    syslog(LOG_INFO, "Skipped authentication, SecureEye is disabled");
    return PAM_AUTHINFO_UNAVAIL;
  }

  // Stop if we're in a remote shell and configured to exit
  if (config.GetBoolean("core", "abort_if_ssh", true)) {
    if (checkenv("SSH_CONNECTION") || checkenv("SSH_CLIENT") ||
        checkenv("SSH_TTY") || checkenv("SSHD_OPTS")) {
      syslog(LOG_INFO, "Skipped authentication, SSH session detected");
      return PAM_AUTHINFO_UNAVAIL;
    }
  }

  // Try to detect the laptop lid state and stop if it's closed
  if (config.GetBoolean("core", "abort_if_lid_closed", true)) {
    glob_t glob_result;

    // Get any files containing lid state
    int return_value =
        glob("/proc/acpi/button/lid/*/state", 0, nullptr, &glob_result);

    if (return_value != 0) {
      syslog(LOG_ERR, "Failed to read files from glob: %d", return_value);
      if (errno != 0) {
        syslog(LOG_ERR, "Underlying error: %s (%d)", strerror(errno), errno);
      }
    } else {
      for (size_t i = 0; i < glob_result.gl_pathc; i++) {
        std::ifstream file(std::string(glob_result.gl_pathv[i]));
        std::string lid_state;
        std::getline(file, lid_state, static_cast<char>(file.eof()));

        if (lid_state.find("closed") != std::string::npos) {
          globfree(&glob_result);

          syslog(LOG_INFO, "Skipped authentication, closed lid detected");
          return PAM_AUTHINFO_UNAVAIL;
        }
      }
    }
    globfree(&glob_result);
  }

  // pre-check if this user has face model file
  auto model_path = std::string(USER_MODELS_DIR) + "/" + username + ".dat";
  struct stat stat_;
  if (stat(model_path.c_str(), &stat_) != 0) {
    return PAM_AUTHINFO_UNAVAIL;
  }

  return PAM_SUCCESS;
}

/**
 * The main function, runs the identification and authentication
 * @param  pamh     The handle to interface directly with PAM
 * @param  flags    Flags passed on to us by PAM, XORed
 * @param  argc     Amount of rules in the PAM config (disregarded)
 * @param  argv     Options defined in the PAM config
 * @param  ask_auth_tok True if we should ask for a password too
 * @return          Returns a PAM return code
 */
auto identify(pam_handle_t *pamh, int flags, int argc, const char **argv,
              bool ask_auth_tok) -> int {
  INIReader config(CONFIG_FILE_PATH);
  openlog("pam_secureEye", 0, LOG_AUTHPRIV);

  // Error out if we could not read the config file
  if (config.ParseError() != 0) {
    syslog(LOG_ERR, "Failed to parse the configuration file: %d",
           config.ParseError());
    return PAM_SYSTEM_ERR;
  }

  // Will contain the responses from PAM functions
  int pam_res = PAM_IGNORE;

  // Get the username from PAM, needed to match correct face model
  char *username = nullptr;
  pam_res = pam_get_user(pamh, const_cast<const char **>(&username), nullptr);
  if (pam_res != PAM_SUCCESS) {
    syslog(LOG_ERR, "Failed to get username");
    return pam_res;
  }

  // Check if we should continue
  pam_res = check_enabled(config, username);
  if (pam_res != PAM_SUCCESS) {
    return pam_res;
  }

  Workaround workaround =
      get_workaround(config.GetString("core", "workaround", "input"));

  // Will contain PAM conversation structure
  struct pam_conv *conv = nullptr;
  const void **conv_ptr =
      const_cast<const void **>(reinterpret_cast<void **>(&conv));

  // Retrieve the PAM conversation structure
  pam_res = pam_get_item(pamh, PAM_CONV, conv_ptr);
  if (pam_res != PAM_SUCCESS) {
    syslog(LOG_ERR, "Failed to acquire conversation");
    return pam_res;
  }

  // Wrap the PAM conversation function in our own, easier function
  auto conv_function = [conv](int msg_type, const char *msg_str) {
    const struct pam_message msg = {.msg_style = msg_type, .msg = msg_str};
    const struct pam_message *msgp = &msg;

    struct pam_response res = {};
    struct pam_response *resp = &res;

    return conv->conv(1, &msgp, &resp, conv->appdata_ptr);
  };

  // Initialize gettext
  setlocale(LC_ALL, "");
  bindtextdomain(GETTEXT_PACKAGE, LOCALEDIR);
  textdomain(GETTEXT_PACKAGE);

  if (config.GetBoolean("core", "detection_notice", true)) {
    if ((conv_function(PAM_TEXT_INFO, S("Attempting facial authentication"))) !=
        PAM_SUCCESS) {
      syslog(LOG_ERR, "Failed to send detection notice");
    }
  }

  // NOTE: We should replace mutex and condition_variable by atomic wait, but
  // it's too recent (C++20)
  std::mutex mutx;
  std::condition_variable convar;
  ConfirmationType confirmation_type(ConfirmationType::Unset);

  // This task sends auth request to authd and waits for response.
  optional_task<int> auth_task([&] {
    int status = authd_authenticate(pamh, username);
    {
      std::unique_lock<std::mutex> lock(mutx);
      if (confirmation_type == ConfirmationType::Unset) {
        confirmation_type = ConfirmationType::SecureEye;
      }
    }
    convar.notify_one();

    return status;
  });
  auth_task.activate();

  // This task waits for the password input (if the workaround wants it)
  optional_task<std::tuple<int, char *>> pass_task([&] {
    char *auth_tok_ptr = nullptr;
    int pam_res = pam_get_authtok(
        pamh, PAM_AUTHTOK, const_cast<const char **>(&auth_tok_ptr), nullptr);
    {
      std::unique_lock<std::mutex> lock(mutx);
      if (confirmation_type == ConfirmationType::Unset) {
        confirmation_type = ConfirmationType::Pam;
      }
    }
    convar.notify_one();

    return std::tuple<int, char *>(pam_res, auth_tok_ptr);
  });

  auto ask_pass = ask_auth_tok && workaround != Workaround::Off;

  // We ask for the password if the function requires it and if a workaround is
  // set
  if (ask_pass) {
    pass_task.activate();
  }

  // Wait for the end either of the child or the password input
  {
    std::unique_lock<std::mutex> lock(mutx);
    convar.wait(lock,
                [&] { return confirmation_type != ConfirmationType::Unset; });
  }

  // The password has been entered or an error has occurred
  if (confirmation_type == ConfirmationType::Pam) {
    // Cancel auth request thread if password flow won the race.
    auth_task.stop(true);

    // We just wait for the thread to stop since it's this one which sent us the
    // confirmation type
    pass_task.stop(false);

    char *password = nullptr;
    std::tie(pam_res, password) = pass_task.get();

    if (pam_res != PAM_SUCCESS) {
      return pam_res;
    }

    // The password has been entered, we are passing it to PAM stack
    return PAM_IGNORE;
  }

  // authd request has finished.
  auth_task.stop(false);

  // Get authd result code.
  int status = auth_task.get();

  // If authd reported a failure while password fallback is active.
  // Do not send enter presses or terminate the PAM function, as the user might
  // still be typing their password
  if (status != EXIT_SUCCESS && ask_pass) {
    // Wait for the password to be typed
    pass_task.stop(false);

    char *password = nullptr;
    std::tie(pam_res, password) = pass_task.get();

    if (pam_res != PAM_SUCCESS) {
      return secureEye_status(username, status, config, conv_function);
    }

    // The password has been entered, we are passing it to PAM stack
    return PAM_IGNORE;
  }

  if (ask_pass) {
    // We want to stop the password prompt, either by canceling the thread when
    // workaround is set to "native", or by emulating "Enter" input with
    // "input".

    // UNSAFE: We cancel the thread using pthread, pam_get_authtok seems to be
    // a cancellation point.
    if (workaround == Workaround::Native) {
      pass_task.stop(true);
    } else if (workaround == Workaround::Input) {
      // We check if we have the right permissions on /dev/uinput
      if (euidaccess("/dev/uinput", W_OK | R_OK) != 0) {
        syslog(LOG_WARNING, "Insufficient permissions to create the fake device");
        conv_function(PAM_ERROR_MSG,
                      S("Insufficient permissions to send Enter "
                        "press, waiting for user to press it instead"));
      } else {
        try {
          EnterDevice enter_device;
          int retries;

          // We try to send it
          enter_device.send_enter_press();

          for (retries = 0;
               retries < MAX_RETRIES &&
               pass_task.wait(DEFAULT_TIMEOUT) == std::future_status::timeout;
               retries++) {
            enter_device.send_enter_press();
          }

          if (retries == MAX_RETRIES) {
            syslog(LOG_WARNING,
                   "Failed to send enter input before the retries limit");
            conv_function(PAM_ERROR_MSG, S("Failed to send Enter press, waiting "
                                           "for user to press it instead"));
          }
        } catch (std::runtime_error &err) {
          syslog(LOG_WARNING, "Failed to send enter input: %s", err.what());
          conv_function(PAM_ERROR_MSG, S("Failed to send Enter press, waiting "
                                         "for user to press it instead"));
        }
      }

      // We stop the thread (will block until the enter key is pressed if the
      // input wasn't focused or if the uinput device failed to send keypress)
      pass_task.stop(false);
    }
  }

  return secureEye_status(username, status, config, conv_function);
}

// Called by PAM when a user needs to be authenticated, for example by running
// the sudo command
PAM_EXTERN auto pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc,
                                    const char **argv) -> int {
  return identify(pamh, flags, argc, argv, true);
}

// Called by PAM when a session is started, such as by the su command
PAM_EXTERN auto pam_sm_open_session(pam_handle_t *pamh, int flags, int argc,
                                    const char **argv) -> int {
  return identify(pamh, flags, argc, argv, false);
}

// The functions below are required by PAM, but not needed in this module
PAM_EXTERN auto pam_sm_acct_mgmt(pam_handle_t *pamh, int flags, int argc,
                                 const char **argv) -> int {
  return PAM_IGNORE;
}
PAM_EXTERN auto pam_sm_close_session(pam_handle_t *pamh, int flags, int argc,
                                     const char **argv) -> int {
  return PAM_IGNORE;
}
PAM_EXTERN auto pam_sm_chauthtok(pam_handle_t *pamh, int flags, int argc,
                                 const char **argv) -> int {
  return PAM_IGNORE;
}
PAM_EXTERN auto pam_sm_setcred(pam_handle_t *pamh, int flags, int argc,
                               const char **argv) -> int {
  return PAM_IGNORE;
}
