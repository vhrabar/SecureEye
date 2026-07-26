#include <QApplication>

#include "main_window.hpp"

auto main(int argc, char *argv[]) -> int {
  QApplication app(argc, argv);
  QCoreApplication::setOrganizationName("vhrabar");
  QCoreApplication::setOrganizationDomain("vhrabar.github.io");
  QApplication::setApplicationName("SecureEye");

  MainWindow window;
  window.resize(500, 400);
  window.show();

  return QApplication::exec();
}
