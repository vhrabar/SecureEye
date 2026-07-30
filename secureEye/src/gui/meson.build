if not meson.version().version_compare('>=1.7')
    error('Building the GUI needs meson >= 1.7 for qt.qml_module(), got ' + meson.version() + '. Configure with -Dinstall_gui=false to skip it.')
endif

qt6 = import('qt6')
qt6_dep = dependency('qt6', modules : ['Core', 'Gui', 'Qml', 'Quick', 'QuickControls2', 'Network'])
gui_inc = include_directories('src', 'src/core')
moc_files = qt6.preprocess(
    moc_headers : [
        'src/app/Application.hpp',
    ],
    qresources : ['secureeye-gui.qrc'],
    dependencies : qt6_dep,
)

# The QML files and the C++ types they use form one QML module. qmltyperegistrar
qml_module = qt6.qml_module(
    'SecureEye.Gui',
    version : '1.0',
    qml_sources : [
        'qml/Main.qml',
        'qml/pages/Dashboard.qml',
        'qml/pages/Configuration.qml',
    ],
    moc_headers : [
        'src/core/ConfigSchema.hpp',
        'src/core/ConfigStore.hpp',
        'src/core/ConfigModel.hpp',
        'src/core/ConfigSectionFilter.hpp',
    ],
    include_directories : gui_inc,
    dependencies : qt6_dep,
    install : false,
)

gui_conf_data = configuration_data(paths_dict)
gui_conf_data.set('config_file_path', config_path)
gui_conf_data.set('py_sources_dir', pysourcesrootdir)

gui_paths_h = configure_file(
    #input : 'paths.hh.in',
    output : 'paths.hh',
    configuration : gui_conf_data,
)

gui_sources = [
    'src/main.cpp',
    'src/app/Application.cpp',
    'src/core/ConfigStore.cpp',
    'src/core/ConfigModel.cpp',
    'src/core/ConfigSectionFilter.cpp',
    'src/core/IniDocument.cpp',
    gui_paths_h,
]

executable(
    'secureeye-gui',
    gui_sources,
    moc_files,
    qml_module,
    include_directories : gui_inc,
    dependencies : [qt6_dep],
    cpp_args : [
        '-DAUTHD_SOCKET_PATH="' + get_option('authd_socket_path') + '"',
        '-DSECUREEYE_CONFIG_PATH="' + config_path + '"',
    ],
    install : true,
    install_dir : get_option('bindir'),
    install_tag : 'gui',
)

install_data(
    'secureeye-gui.desktop',
    install_dir : join_paths(get_option('prefix'), get_option('datadir'), 'applications'),
    install_tag : 'gui',
)

install_data(
    'icons/logo.svg',
    rename : 'secureeye.svg',
    install_dir : join_paths(get_option('prefix'), get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps'),
    install_tag : 'gui',
)
