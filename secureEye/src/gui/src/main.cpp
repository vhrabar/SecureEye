#include "app/Application.hpp"

auto main(int argc, char *argv[]) -> int {
  // ReSharper disable once CppTooWideScopeInitStatement
  Application app(argc, argv);
  if (!app.bootstrap()) {
    return 1;
  }

  return Application::exec();
}
