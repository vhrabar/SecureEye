#ifndef SECUREEYE_APPLICATION_HPP
#define SECUREEYE_APPLICATION_HPP

#include <QGuiApplication>
#include <QQmlApplicationEngine>

class Application : public QGuiApplication {
    Q_OBJECT

public:
    Application(int& argc, char** argv);
    ~Application() override;

    bool bootstrap();

private:
    void createServices();
    void exposeToQml();
    void loadQml();

    QQmlApplicationEngine m_engine;
    bool m_qmlLoaded = false;
};

#endif // SECUREEYE_APPLICATION_HPP
