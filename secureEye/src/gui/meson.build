qt6 = import('qt6')
qt6_dep = dependency('qt6', modules : ['Core', 'Gui', 'Widgets', 'Network'])

moc_files = qt6.preprocess(
    moc_headers : [],
    dependencies : qt6_dep,
)

executable(
    'secureeye-gui',
    'main.cc',
    moc_files,
    dependencies : [qt6_dep],
    cpp_args : [
        '-DAUTHD_SOCKET_PATH="' + get_option('authd_socket_path') + '"',
    ],
    install : true,
    install_dir : get_option('bindir'),
    install_tag : 'gui',
)
