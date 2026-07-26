#ifndef MAIN_WINDOW_HPP
#define MAIN_WINDOW_HPP

#include <QMainWindow>


class QLabel;
class QLineEdit;
class QPushButton;

class MainWindow : public QMainWindow {
	Q_OBJECT

public:
	explicit MainWindow(QWidget *parent = nullptr);

private:
};

#endif // MAIN_WINDOW_HPP
