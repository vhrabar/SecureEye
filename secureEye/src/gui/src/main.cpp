#include "app/Application.hpp"

#include <unistd.h>

#include <cstdio>

auto main(int argc, char* argv[]) -> int {
    // Privileged actions go through pkexec one command at a time.
    if (geteuid() == 0) {
        std::fputs("secureeye-gui must not be run as root. Start it as your normal user; it asks for administrator "
                   "rights through polkit only for the actions that need them.\n",
                   stderr);
        return 1;
    }

    // ReSharper disable once CppTooWideScopeInitStatement
    Application app(argc, argv);
    if (!app.bootstrap()) {
        return 1;
    }

    return Application::exec();
}
