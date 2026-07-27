qt6 = import('qt6')
qt6_dep = dependency('qt6', modules : ['Core', 'Gui', 'Qml', 'Quick', 'QuickControls2', 'Network'])
moc_files = qt6.preprocess(
    moc_headers : [
        'src/app/Application.hpp',
        'src/core/ConfigStore.hpp',
        'src/core/ConfigSchema.hpp'
    ],
    qresources : ['secureeye-gui.qrc'],
    dependencies : qt6_dep,
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
    gui_paths_h,
]

executable(
    'secureeye-gui',
    gui_sources,
    moc_files,
    dependencies : [qt6_dep],
    cpp_args : [
        '-DAUTHD_SOCKET_PATH="' + get_option('authd_socket_path') + '"',
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
