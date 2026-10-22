if not meson.version().version_compare('>=1.7')
    error('Building the GUI needs meson >= 1.7 for qt.qml_module(), got ' + meson.version() + '. Configure with -Dinstall_gui=false to skip it.')
endif

qt6 = import('qt6')
qt6_dep = dependency('qt6', modules : ['Core', 'DBus', 'Gui', 'Qml', 'Quick', 'QuickControls2', 'Network'])
gui_inc = include_directories('src', 'src/core', 'src/system')
moc_files = qt6.preprocess(
    moc_headers : [
        'src/app/Application.hpp',
        'src/system/AuthdRequest.hpp',
        'src/system/GuiBackend.hpp',
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
        'qml/controls/ConfigRow.qml',
        'qml/components/CameraPreview.qml',
        'qml/components/SectionHeading.qml',
        'qml/components/SelectRow.qml',
        'qml/components/SliderRow.qml',
        'qml/components/SpinRow.qml',
        'qml/components/StatusCard.qml',
        'qml/components/TextRow.qml',
        'qml/components/ToggleRow.qml',
    ],
    moc_headers : [
        'src/core/ConfigSchema.hpp',
        'src/core/ConfigStore.hpp',
        'src/core/ConfigModel.hpp',
        'src/core/ConfigSectionFilter.hpp',
        'src/system/CameraSession.hpp',
        'src/system/DaemonController.hpp',
        'src/system/ModelStore.hpp',
        'src/system/PamStatus.hpp',
        'src/system/PreviewImage.hpp',
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
    'src/system/AuthdRequest.cpp',
    'src/system/CameraSession.cpp',
    'src/system/DaemonController.cpp',
    'src/system/GuiBackend.cpp',
    'src/system/ModelStore.cpp',
    'src/system/PamStatus.cpp',
    'src/system/PreviewImage.cpp',
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
        '-DSECUREEYE_CLI_PATH="' + join_paths(get_option('prefix'), get_option('bindir'), 'secureEye') + '"',
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

qt6_test_dep = dependency('qt6', modules : ['Core', 'Gui', 'Network', 'Qml', 'Quick', 'Test'], required : false)
if qt6_test_dep.found()
    test_configstore_moc = qt6.preprocess(
        moc_headers : ['src/core/ConfigStore.hpp', 'src/system/GuiBackend.hpp'],
        moc_sources : ['tests/test_configstore.cpp'],
        include_directories : gui_inc,
        dependencies : qt6_test_dep,
    )
    test_configstore = executable(
        'test_configstore',
        'tests/test_configstore.cpp',
        'src/core/ConfigStore.cpp',
        'src/core/IniDocument.cpp',
        'src/system/GuiBackend.cpp',
        test_configstore_moc,
        include_directories : gui_inc,
        dependencies : qt6_test_dep,
        cpp_args : [
            '-DSHIPPED_CONFIG_PATH="' + join_paths(meson.current_source_dir(), '..', 'config.ini') + '"',
            '-DSECUREEYE_CONFIG_PATH="' + config_path + '"',
            '-DSECUREEYE_CLI_PATH="' + join_paths(get_option('prefix'), get_option('bindir'), 'secureEye') + '"',
        ],
        install : false,
    )
    test('configstore', test_configstore, env : ['QT_QPA_PLATFORM=offscreen'])

    test_authdrequest_moc = qt6.preprocess(
        moc_headers : ['src/system/AuthdRequest.hpp'],
        moc_sources : ['tests/test_authdrequest.cpp'],
        include_directories : gui_inc,
        dependencies : qt6_test_dep,
    )
    test_authdrequest = executable(
        'test_authdrequest',
        'tests/test_authdrequest.cpp',
        'src/system/AuthdRequest.cpp',
        test_authdrequest_moc,
        include_directories : gui_inc,
        dependencies : qt6_test_dep,
        cpp_args : ['-DAUTHD_SOCKET_PATH="' + get_option('authd_socket_path') + '"'],
        install : false,
    )
    test('authdrequest', test_authdrequest, env : ['QT_QPA_PLATFORM=offscreen'])

    test_modelstore_moc = qt6.preprocess(
        moc_headers : ['src/system/AuthdRequest.hpp', 'src/system/ModelStore.hpp'],
        moc_sources : ['tests/test_modelstore.cpp'],
        include_directories : gui_inc,
        dependencies : qt6_test_dep,
    )
    test_modelstore = executable(
        'test_modelstore',
        'tests/test_modelstore.cpp',
        'src/system/AuthdRequest.cpp',
        'src/system/ModelStore.cpp',
        test_modelstore_moc,
        include_directories : gui_inc,
        dependencies : qt6_test_dep,
        cpp_args : ['-DAUTHD_SOCKET_PATH="' + get_option('authd_socket_path') + '"'],
        install : false,
    )
    test('modelstore', test_modelstore, env : ['QT_QPA_PLATFORM=offscreen'])

    test_camerasession_moc = qt6.preprocess(
        moc_headers : [
            'src/system/AuthdRequest.hpp',
            'src/system/CameraSession.hpp',
            'src/system/ModelStore.hpp',
            'src/system/PreviewImage.hpp',
        ],
        moc_sources : ['tests/test_camerasession.cpp'],
        include_directories : gui_inc,
        dependencies : qt6_test_dep,
    )
    test_camerasession = executable(
        'test_camerasession',
        'tests/test_camerasession.cpp',
        'src/system/AuthdRequest.cpp',
        'src/system/CameraSession.cpp',
        'src/system/ModelStore.cpp',
        'src/system/PreviewImage.cpp',
        test_camerasession_moc,
        include_directories : gui_inc,
        dependencies : qt6_test_dep,
        cpp_args : ['-DAUTHD_SOCKET_PATH="' + get_option('authd_socket_path') + '"'],
        install : false,
    )
    test('camerasession', test_camerasession, env : ['QT_QPA_PLATFORM=offscreen'])
endif
