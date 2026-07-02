#include <QApplication>

#include "main_window.hh"

int main(int argc, char *argv[]) {
  QApplication app(argc, argv);
  QCoreApplication::setOrganizationName("vhrabar");
  QCoreApplication::setOrganizationDomain("vhrabar.github.io");
  QApplication::setApplicationName("SecureEye");

  MainWindow window;
  window.resize(500, 400);
  window.show();

  return app.exec();
}
