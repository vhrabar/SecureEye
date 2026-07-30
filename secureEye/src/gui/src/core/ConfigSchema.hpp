#ifndef SECUREEYE_CONFIGSCHEMA_HPP
#define SECUREEYE_CONFIGSCHEMA_HPP

#include <QObject>

#include <algorithm>
#include <array>
#include <cstdint>
#include <span>
#include <string_view>

namespace secureEye::config {
Q_NAMESPACE

enum class ValueType : std::uint8_t {
    Bool,
    Int,
    Float,
    String,
    Enum,
    Path,
    Multiline,
};

Q_ENUM_NS(ValueType)

// One editable key of config.ini -> single TS
struct ConfigOption {
    std::string_view section;
    std::string_view key;
    ValueType type;

    std::string_view defaultValue;
    std::string_view label;
    std::string_view help;

    std::span<const std::string_view> enumValues;
    std::span<const std::string_view> enumLabels;

    bool hasRange = false;
    double min = 0.0;
    double max = 0.0;

    // Recorder the option is limited to, when it is not universal.
    std::string_view note;

    std::string_view requiresKey;
    std::string_view requiresValue;
};

struct ConfigSectionInfo {
    std::string_view name;
    std::string_view title;
    std::string_view description;
};

inline constexpr std::array<std::string_view, 2> kDetectorBackends = {
    "dlib",
    "mediapipe",
};
inline constexpr std::array<std::string_view, 2> kDetectorBackendLabels = {
    "Dlib",
    "MediaPipe",
};
inline constexpr std::array<std::string_view, 3> kWorkarounds = {
    "off",
    "input",
    "native",
};
inline constexpr std::array<std::string_view, 3> kWorkaroundLabels = {
    "Off - press enter yourself after a timeout",
    "Input - send an enter keypress",
    "Native - stop the prompt in PAM (can be unstable)",
};
inline constexpr std::array<std::string_view, 3> kRecordingPlugins = {
    "opencv",
    "ffmpeg",
    "pyv4l2",
};
inline constexpr std::array<std::string_view, 2> kDeviceFormats = {
    "vfwcap",
    "v4l2",
};
inline constexpr std::array<std::string_view, 3> kRotateModes = {
    "0",
    "1",
    "2",
};
inline constexpr std::array<std::string_view, 3> kRotateModeLabels = {
    "Landscape only",
    "Landscape and portrait",
    "Portrait only",
};

inline constexpr auto kSections = std::to_array<ConfigSectionInfo>({
    {.name = "core", .title = "Core", .description = "PAM behaviour, notices and the face detector backend."},
    {.name = "video", .title = "Video", .description = "Capture device, timeout and recognition certainty."},
    {.name = "snapshots", .title = "Snapshots", .description = "Saving snapshots of failed and successful attempts."},
    {.name = "debug", .title = "Debug", .description = "Diagnostic reports and verbose logging."},
});

inline constexpr auto kOptions = std::to_array<ConfigOption>({
    // [core]
    {.section = "core",
     .key = "detection_notice",
     .type = ValueType::Bool,
     .defaultValue = "false",
     .label = "Announce detection attempts",
     .help = "Print that face detection is being attempted."},
    {.section = "core",
     .key = "timeout_notice",
     .type = ValueType::Bool,
     .defaultValue = "true",
     .label = "Announce timeouts",
     .help = "Print that face detection has timed out."},
    {.section = "core",
     .key = "no_confirmation",
     .type = ValueType::Bool,
     .defaultValue = "false",
     .label = "Silent on success",
     .help = "Do not print anything when a face verification succeeds."},
    {.section = "core",
     .key = "suppress_unknown",
     .type = ValueType::Bool,
     .defaultValue = "false",
     .label = "Suppress unknown users",
     .help = "When a user without a known face model tries to authenticate, fail "
             "silently instead of showing an error."},
    {.section = "core",
     .key = "abort_if_ssh",
     .type = ValueType::Bool,
     .defaultValue = "true",
     .label = "Disable over SSH",
     .help = "Disable SecureEye in remote shells."},
    {.section = "core",
     .key = "abort_if_lid_closed",
     .type = ValueType::Bool,
     .defaultValue = "true",
     .label = "Disable with the lid closed",
     .help = "Disable SecureEye while the laptop lid is closed."},
    {.section = "core",
     .key = "disabled",
     .type = ValueType::Bool,
     .defaultValue = "false",
     .label = "Disable face authentication",
     .help = "Disable SecureEye in PAM. The secureEye command still functions."},
    {.section = "core",
     .key = "detector_backend",
     .type = ValueType::Enum,
     .defaultValue = "mediapipe",
     .label = "Detector backend",
     .help = "Face detector used by the auth and session flow. Dlib uses its own "
             "detector and encoder, MediaPipe uses FaceNet-style embeddings.",
     .enumValues = kDetectorBackends,
     .enumLabels = kDetectorBackendLabels},
    {.section = "core",
     .key = "use_cnn",
     .type = ValueType::Bool,
     .defaultValue = "false",
     .label = "Use the CNN model",
     .help = "Much more accurate than the HOG based model, but it needs a GPU "
             "to run "
             "at a reasonable speed."},
    {
        .section = "core",
        .key = "workaround",
        .type = ValueType::Enum,
        .defaultValue = "off",
        .label = "Password prompt workaround",
        .help = "How to do face and password authentication at the same time.",
        .enumValues = kWorkarounds,
        .enumLabels = kWorkaroundLabels,
    },

    // [video]
    {.section = "video",
     .key = "certainty",
     .type = ValueType::Float,
     .defaultValue = "3.5",
     .label = "Certainty",
     .help = "How certain the match between the detected face and the account "
             "owner "
             "has to be. Lower is stricter; values above 5 are not recommended.",
     .hasRange = true,
     .min = 1.0,
     .max = 10.0},
    {
        .section = "video",
        .key = "timeout",
        .type = ValueType::Int,
        .defaultValue = "4",
        .label = "Timeout",
        .help = "Number of seconds to search for a face before giving up.",
        .hasRange = true,
        .min = 1.0,
        .max = 60.0,
    },
    {.section = "video",
     .key = "device_path",
     .type = ValueType::Path,
     .defaultValue = "none",
     .label = "Camera device",
     .help = "Path of the device to capture frames from. Video devices are usually "
             "found in /dev/v4l/by-path/."},
    {.section = "video",
     .key = "warn_no_device",
     .type = ValueType::Bool,
     .defaultValue = "true",
     .label = "Warn if the device is missing",
     .help = "Print a warning if the video device is not found."},
    {
        .section = "video",
        .key = "max_height",
        .type = ValueType::Int,
        .defaultValue = "320",
        .label = "Maximum frame height",
        .help = "Scale the video feed down to this height. Speeds up face "
                "recognition "
                "but can make it less precise.",
        .hasRange = true,
        .min = 0.0,
        .max = 2160.0,
    },
    {.section = "video",
     .key = "frame_width",
     .type = ValueType::Int,
     .defaultValue = "-1",
     .label = "Frame width",
     .help = "Camera input profile width. The largest profile is used when set "
             "to -1, "
             "and invalid profiles are ignored.",
     .hasRange = true,
     .min = -1.0,
     .max = 7680.0},
    {.section = "video",
     .key = "frame_height",
     .type = ValueType::Int,
     .defaultValue = "-1",
     .label = "Frame height",
     .help = "Camera input profile height. The largest profile is used when "
             "set to -1, "
             "and invalid profiles are ignored.",
     .hasRange = true,
     .min = -1.0,
     .max = 4320.0},
    {
        .section = "video",
        .key = "dark_threshold",
        .type = ValueType::Int,
        .defaultValue = "60",
        .label = "Dark frame threshold",
        .help = "Skip a frame if the lowest eighth of its histogram is above this "
                "percentage of the total. Lower values ignore more dark frames.",
        .hasRange = true,
        .min = 0.0,
        .max = 100.0,
    },
    {
        .section = "video",
        .key = "recording_plugin",
        .type = ValueType::Enum,
        .defaultValue = "opencv",
        .label = "Recorder",
        .help = "Recorder used to capture frames. Switching from opencv to "
                "ffmpeg can "
                "help with grayscale issues.",
        .enumValues = kRecordingPlugins,
    },
    {
        .section = "video",
        .key = "device_format",
        .type = ValueType::Enum,
        .defaultValue = "v4l2",
        .label = "Device format",
        .help = "Video format used to open the capture device.",
        .enumValues = kDeviceFormats,
        .note = "ffmpeg only",
        .requiresKey = "recording_plugin",
        .requiresValue = "ffmpeg",
    },
    {
        .section = "video",
        .key = "force_mjpeg",
        .type = ValueType::Bool,
        .defaultValue = "false",
        .label = "Force Motion JPEG",
        .help = "Force the use of Motion JPEG when decoding frames, which "
                "fixes issues "
                "with YUYV raw frame decoding.",
        .note = "opencv only",
        .requiresKey = "recording_plugin",
        .requiresValue = "opencv",
    },
    {
        .section = "video",
        .key = "exposure",
        .type = ValueType::Int,
        .defaultValue = "-1",
        .label = "Exposure",
        .help = "Explicit exposure value, which disables autoexposure. Use "
                "qv4l2 to "
                "determine an appropriate value. -1 keeps autoexposure.",
        .hasRange = true,
        .min = -1.0,
        .max = 10000.0,
        .note = "opencv only",
        .requiresKey = "recording_plugin",
        .requiresValue = "opencv",
    },
    {
        .section = "video",
        .key = "device_fps",
        .type = ValueType::Int,
        .defaultValue = "-1",
        .label = "Frame rate",
        .help = "Frame rate of the capture device. Some IR emitters do not work "
                "properly "
                "at the default rate. -1 keeps the device default.",
        .hasRange = true,
        .min = -1.0,
        .max = 1000.0,
        .note = "opencv only",
        .requiresKey = "recording_plugin",
        .requiresValue = "opencv",
    },
    {.section = "video",
     .key = "rotate",
     .type = ValueType::Enum,
     .defaultValue = "0",
     .label = "Frame orientation",
     .help = "Rotate captured frames so that faces are upright.",
     .enumValues = kRotateModes,
     .enumLabels = kRotateModeLabels},

    // [snapshots]
    {
        .section = "snapshots",
        .key = "save_failed",
        .type = ValueType::Bool,
        .defaultValue = "false",
        .label = "Save failed attempts",
        .help = "Capture snapshots of failed login attempts and save them with "
                "metadata "
                "to /var/log/secureEye/snapshots.",
    },
    {
        .section = "snapshots",
        .key = "save_successful",
        .type = ValueType::Bool,
        .defaultValue = "false",
        .label = "Save successful attempts",
        .help = "Also capture snapshots of successful login attempts.",
    },

    // [debug]
    {
        .section = "debug",
        .key = "end_report",
        .type = ValueType::Bool,
        .defaultValue = "false",
        .label = "Diagnostic report",
        .help = "Show a short but detailed diagnostic report in the console. "
                "Enabling "
                "this can make some UI apps fail, only use it to debug.",
    },
    {
        .section = "debug",
        .key = "verbose_stamps",
        .type = ValueType::Bool,
        .defaultValue = "false",
        .label = "Verbose rubberstamps",
        .help = "More verbose logging from the rubberstamps system.",
    },
    {
        .section = "debug",
        .key = "gtk_stdout",
        .type = ValueType::Bool,
        .defaultValue = "false",
        .label = "GTK window output",
        .help = "Pass output of the GTK auth window to the terminal.",
    },
});

[[nodiscard]] constexpr auto options() -> std::span<const ConfigOption> {
    return kOptions;
}

[[nodiscard]] constexpr auto sections() -> std::span<const ConfigSectionInfo> {
    return kSections;
}

[[nodiscard]] constexpr auto findOption(const std::string_view section,
                                        const std::string_view key) -> const ConfigOption* {
    const auto* const match = std::ranges::find_if(
        kOptions, [&](const ConfigOption& option) -> bool { return option.section == section && option.key == key; });

    return match == std::ranges::end(kOptions) ? nullptr : &*match;
}

[[nodiscard]] constexpr auto findSection(const std::string_view section) -> const ConfigSectionInfo* {
    const auto* const match =
        std::ranges::find_if(kSections, [&](const ConfigSectionInfo& info) -> bool { return info.name == section; });

    return match == std::ranges::end(kSections) ? nullptr : &*match;
}

[[nodiscard]] constexpr auto typeName(const ValueType type) -> std::string_view {
    switch (type) {
    case ValueType::Bool:
        return "bool";
    case ValueType::Int:
        return "int";
    case ValueType::Float:
        return "float";
    case ValueType::String:
        return "string";
    case ValueType::Enum:
        return "enum";
    case ValueType::Path:
        return "path";
    case ValueType::Multiline:
        return "multiline";
    }

    return "string";
}

} // namespace secureEye::config

#endif // SECUREEYE_CONFIGSCHEMA_HPP
