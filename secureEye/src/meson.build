if meson.is_subproject()
project('secureEye', 'cpp', license: 'GPLv2', version: 'beta', meson_version: '>= 0.64.0')
endif


datadir = get_option('prefix') / get_option('datadir') / 'secureEye'
py_conf = configuration_data(paths_dict)
py_conf.set('data_dir', datadir)

py = import('python').find_installation(paths_dict.get('python_path'))

py_paths = configure_file(
    input: 'paths.py.in',
    output: 'paths.py',
    configuration: py_conf,
)

py_sources = [
    'authd/__init__.py',
    'authd/main.py',
    'authd/protocol.py',
    'authd/server.py',
    'auth/__init__.py',
    'auth/detector_factory.py',
    'auth/errors.py',
    'auth/frame_ops.py',
    'auth/matching.py',
    'auth/model_store.py',
    'auth/session.py',
    'auth/types.py',
    'auth/ui_bridge.py',
    'cli/__init__.py',
    'cli/add.py',
    'cli/clear.py',
    'cli/config.py',
    'cli/disable.py',
    'cli/list.py',
    'cli/remove.py',
    'cli/set.py',
    'cli/snap.py',
    'cli/test.py',
    'cli.py',
    'compare.py',
    'detectors/__init__.py',
    'detectors/base.py',
    'detectors/dlib_detector.py',
    'detectors/mediapipe_detector.py',
    'detectors/utils.py',
    'i18n.py',
    'paths_factory.py',
    'recorders/__init__.py',
    'recorders/ffmpeg_reader.py',
    'recorders/pyv4l2_reader.py',
    'recorders/v4l2.py',
    'recorders/video_capture.py',
    'rubberstamps/__init__.py',
    'rubberstamps/hotkey.py',
    'rubberstamps/nod.py',
    'snapshot.py',
    py_paths,
]

# Include PAM module
if get_option('install_in_site_packages')
    pysourcesrootdir = py.get_install_dir()
else
    pysourcesrootdir = get_option('py_sources_dir') != '' ? get_option('py_sources_dir') : join_paths(get_option('prefix'), get_option('libdir'))
endif
pysourcesinstalldir = join_paths(pysourcesrootdir, 'secureEye')

pam_module_conf_data = configuration_data(paths_dict)
pam_module_conf_data.set('compare_script_path', join_paths(pysourcesinstalldir, 'compare.py'))
pam_module_conf_data.set('authd_socket_path', get_option('authd_socket_path'))
pam_module_conf_data.set('config_file_path', config_path)
subdir('pam')
if get_option('install_pam_config')
    # pamdir is inherited from the pam subproject
    pam_config = configure_file(
        input: 'pam-config/secureEye.in',
        output: 'pam-config',
        configuration: {'pamdir': pamdir}
    )
    install_data(
        pam_config,
        install_dir: get_option('prefix') / get_option('datadir') / 'pam-configs',
        install_mode: 'rwxr-xr-x',
        install_tag: 'pam',
        rename: 'secureEye',
    )
endif

if get_option('install_in_site_packages')
    py.install_sources(
        py_sources,
        subdir: 'secureEye',
        preserve_path: true,
        install_tag: 'py_sources',
    )
else
    install_data(
        py_sources,
        preserve_path: true,
        install_dir: pysourcesinstalldir,
        install_mode: 'r--r--r--',
        install_tag: 'py_sources',
    )
endif

install_data('logo.png', install_tag: 'meta')
autocomplete = configure_file(
    input: 'autocomplete/secureEye.in',
    output: 'autocomplete',
    configuration: configuration_data({ 'config_path': config_path })
)
install_data(
    autocomplete,
    install_dir: join_paths(get_option('prefix'), get_option('datadir'), 'bash-completion', 'completions'),
    install_mode: 'rwxr--r--',
    install_tag: 'bash_completion',
    rename: 'secureEye',
)

install_data('config.ini', install_dir: confdir, install_mode: 'rwxr--r--', install_tag: 'config')

install_data('dlib-data/install.sh', 'dlib-data/Readme.md', install_dir: dlibdatadir, install_mode: 'rwxr--r--')

install_man('../SecureEye.1')

systemd = dependency('systemd', required : false)
systemd_unit_dir = join_paths(get_option('prefix'), 'lib', 'systemd', 'system')
if systemd.found()
    systemd_unit_dir = systemd.get_variable(
        pkgconfig : 'systemdsystemunitdir',
        default_value : systemd_unit_dir,
    )
endif

authd_service = configure_file(
    input : 'systemd/secureeye-authd.service.in',
    output : 'secureeye-authd.service',
    configuration : configuration_data({
                                           'python_path' : py.full_path(),
                                           'py_sources_dir' : pysourcesrootdir,
                                       }),
)
install_data(
    authd_service,
    install_dir : systemd_unit_dir,
    install_mode : 'rw-r--r--',
    install_tag : 'systemd',
)

# if get_option('fetch_dlib_data')
#     downloader = find_program('wget')
#     bunzip2 = find_program('bunzip2')

#     links = [ 
#         'https://github.com/davisking/dlib-models/raw/master/dlib_face_recognition_resnet_model_v1.dat.bz2',
#         'https://github.com/davisking/dlib-models/raw/master/mmod_human_face_detector.dat.bz2',
#         'https://github.com/davisking/dlib-models/raw/master/shape_predictor_5_face_landmarks.dat.bz2'
#     ]

#     archived_model_files = [
#         'dlib_face_recognition_resnet_model_v1.dat.bz2',
#         'shape_predictor_5_face_landmarks.dat.bz2',
#         'mmod_human_face_detector.dat.bz2'
#     ]

#     download = run_command(
#         'download',
#         links,
#         output: archived_model_files,
#         command: [downloader, '-O', '@OUTPUT@', '@INPUT@']
#     )

#     model_files = [
#         'dlib_face_recognition_resnet_model_v1.dat',
#         'shape_predictor_5_face_landmarks.dat',
#         'mmod_human_face_detector.dat'
#     ]

#     models = custom_target(
#         'models',
#         input: archived_model_files,
#         output: model_files,
#         command: [bunzip2, '-k', '@INPUT@'],
#     )

#     install_data(
#         model_files,
#         install_dir: join_paths(get_option('prefix'), get_option('libdir'), 'dlib_models'),
#     )

# endif

cli_path = join_paths(pysourcesinstalldir, 'cli.py')
authd_python = get_option('prefix') / 'lib' / 'secureeye-authd' / 'venv' / 'bin' / 'python3'
conf_data = configuration_data({
    'script_path': cli_path,
    'python_path': py.full_path(),
    'authd_python': authd_python,
    'py_sources_dir': pysourcesrootdir,
})

bin_name = 'secureEye'
bin = configure_file(
    input: 'bin/secureEye.in',
    output: bin_name,
    configuration: conf_data
)
install_data(
  bin,
  install_mode: 'rwxr-xr-x',
  install_dir: get_option('bindir'),
  install_tag: 'bin',
)
