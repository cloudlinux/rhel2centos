#!/usr/bin/env python

import logging
import platform
import os
import subprocess
import shutil
import json


logger = None

STATUS_JSON_FILE = '/var/run/rhel2centos.status.json'
SUPPORTED_MAJOR_VERSION_OS = 7
SUPPORTED_NAME_OS = 'redhat'


def get_logger():
    # type() -> logging.Logger
    global logger
    if logger is not None:
        return logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('(%(asctime)s) [%(levelname)s] %(message)s')
    file_handler = logging.FileHandler('/var/log/rhel2centos.log')
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def get_stage_status(stage_name):
    # type(str) -> bool
    """
    Get current state of a migration's stage
    :param stage_name: name of a migration's stage
    :return: bool value of state
    """

    if not os.path.exists(STATUS_JSON_FILE):
        return False
    with open(STATUS_JSON_FILE, 'r') as status_file:
        return json.load(status_file).get(stage_name, False)


def set_successful_stage_status(stage_name):
    # type(str) -> None
    """
    Set successful state of a migration's state
    :param stage_name: name of a migration's sate
    :return: None
    """

    if os.path.exists(STATUS_JSON_FILE):
        with open(STATUS_JSON_FILE, 'r') as status_file:
            statuses = json.load(status_file)
    else:
        statuses = {}
    statuses[stage_name] = True
    with open(STATUS_JSON_FILE, 'w') as status_file:
        json.dump(statuses, status_file, indent=4)


def get_os_version_and_name():
    # type() -> tuple(int, int, str)
    """
    Get major, minor versions of OS and it's name
    Returns 0, 0, '' if OS name is empty
    :return: major version, minor version, OS name
    """

    os_name, os_version, _ = platform.dist()
    if os_name == '':
        return 0, 0, ''
    return int(os_version[0]), int(os_version[2]), os_name


def is_conversion_completed():
    # type() -> None
    """
    Check current state of migration.
    Exit from the script if migrations was completed earlier
    :return: None
    """
    if get_stage_status('completed'):
        get_logger().info('The system is already migrated to CentOS 7')
        exit(0)


def is_run_under_root():
    # type() -> None
    """
    The script should be run under root or through sudo or similar utility
    Exit from the script if effective UID isn't equal to zero
    :return: None
    """
    if bool(os.geteuid()):
        get_logger().info(
            'This script should be run under any sudo user',
        )
        exit(0)


def is_efi_system():
    # type() -> bool
    """
    Check existing EFI file system
    :return: True if EFI FS exists, otherwise - False
    """

    return os.path.exists('/sys/firmware/efi')


def is_katello_satelite():
    # type() -> bool
    """
    Check if python-qpid-proton(katello-satellite breaking dependency) is installed
    Also check for python2-qpid-proton(katello-satellite breaking dependency)
    :return: True if installed, otherwise - False
    """
    try:
        subprocess.check_call(
            'rpm -q python-qpid-proton &> /dev/null',
            shell=True,
        )

    except subprocess.CalledProcessError:
        return False
    try:
        subprocess.check_call(
            'rpm -q python2-qpid-proton &> /dev/null',
            shell=True,
        )
    except subprocess.CalledProcessError:
        return False

    return True


def remove_katello_satellite_packages():
    # type() -> None
    """
    Remove katello-satellite packages if those are installed on a system
    :return: None
    """
    if get_stage_status('remove_katello_satellite_packages'):
        return
    removed_pkgs = [
        'python-qpid-proton',
        'katello-agent'
    ]
    get_logger().info(
        'Removing katello-satellite packages: %s',
        ', '.join(removed_pkgs),
    )
    for removed_pkg in removed_pkgs:
        try:
            subprocess.check_call(
                'rpm -q %s &> /dev/null' % removed_pkg,
                shell=True,
            )
        except subprocess.CalledProcessError:
            get_logger().warning(
                'Package "%s" is absent in system',
                removed_pkg,
            )
            continue
        try:
            subprocess.check_output(
                'rpm -e --nodeps %s 2>&1' % removed_pkg,
                shell=True,
            )
            get_logger().info(
                'Package "%s" is removed from system',
                removed_pkg,
            )
        except subprocess.CalledProcessError as error:
            get_logger().error(
                'Some error is occurred while erasing rpm package "%s".\n'
                'Please check the following output:\n'
                '%s',
                removed_pkg,
                error.output,
            )
            exit(1)
    set_successful_stage_status('remove_katello_satellite_packages')


def remove_redhat_packages():
    # type() -> None
    """
    Remove Red Hat related rpm packages if those are installed on a system
    :return: None
    """
    if get_stage_status('remove_redhat_packages'):
        return
    removed_pkgs = [
        'redhat-release-eula',
        'redhat-release-server',
        'redhat-logos',
    ]
    get_logger().info(
        'Remove Red Hat specific packages "%s"',
        removed_pkgs,
    )
    for removed_pkg in removed_pkgs:
        try:
            subprocess.check_call(
                'rpm -q %s &> /dev/null' % removed_pkg,
                shell=True,
            )
        except subprocess.CalledProcessError:
            get_logger().warning(
                'Package "%s" is absent in system',
                removed_pkg,
            )
            continue
        try:
            subprocess.check_output(
                'rpm -e --nodeps %s 2>&1' % removed_pkg,
                shell=True,
            )
            get_logger().info(
                'Package "%s" is removed from system',
                removed_pkg,
            )
        except subprocess.CalledProcessError as error:
            get_logger().error(
                'Some error is occurred while erasing rpm package "%s".\n'
                'Please check the following output:\n'
                '%s',
                removed_pkg,
                error.output,
            )
            exit(1)
    set_successful_stage_status('remove_redhat_packages')


def remove_not_needed_dirs():
    # type() -> None
    """
    Remove not needed directory which prevent installing centos-release package
    :return: None
    """
    if get_stage_status('remove_not_needed_dirs'):
        return
    removed_dirs = [
        '/usr/share/redhat-release',
        '/usr/share/doc/redhat-release',
    ]
    get_logger().info(
        'Remove not needed Red Hat directories "%s"',
        removed_dirs,
    )
    for removed_dir in removed_dirs:
        if os.path.isdir(removed_dir) and not os.path.islink(removed_dir):
            shutil.rmtree(removed_dir)
        else:
            get_logger().info(
                'Directory "%s" is absent in system',
                removed_dir,
            )
    set_successful_stage_status('remove_not_needed_dirs')


def install_centos_packages():
    # type() -> None
    """
    Install CentOS related rpm packages
    :return: None
    """
    if get_stage_status('install_centos_packages'):
        return
    installed_pkgs = {
        'centos-release':
            'http://mirror.centos.org/centos/7/os/x86_64/Packages'
            '/centos-release-7-9.2009.0.el7.centos.x86_64.rpm',
        'centos-logos':
            'http://mirror.centos.org/centos/7/os/x86_64/Packages'
            '/centos-logos-70.0.6-3.el7.centos.noarch.rpm'
    }
    for installed_pkg_name, installed_pkg_url in installed_pkgs.iteritems():
        try:
            get_logger().info(
                'Install CentOS package "%s"',
                installed_pkg_name,
            )
            subprocess.check_output(
                'yum localinstall %s -y &> /dev/null' % installed_pkg_url,
                shell=True,
            )
            get_logger().info(
                'CentOS package "%s" is installed',
                installed_pkg_name,
            )
        except subprocess.CalledProcessError as error:
            get_logger().error(
                'Some error is occurred while installing '
                'CentOS package "%s".\n',
                'Please check the following output:\n'
                '%s',
                installed_pkg_name,
                error.output,
            )
            exit(1)
    set_successful_stage_status('install_centos_packages')


def update_the_system():
    # type() -> None
    """
    Run updating of a system
    :return: None
    """
    if get_stage_status('update_the_system'):
        return
    try:
        get_logger().info('Run updating of system')
        subprocess.check_call(
            'yum update -y',
            shell=True,
        )
    except subprocess.CalledProcessError:
        get_logger().error(
            'Some error is occurred while updating system.'
        )
        exit(1)
    get_logger().info('Updating of system is completed successful')
    set_successful_stage_status('update_the_system')


def synchronization_of_distribution():
    # type() -> None
    """
    Run yum distro-sync
    :return: None
    """
    if get_stage_status('synchronization_of_distribution'):
        return
    try:
        get_logger().info('Run synchronization of distribution')
        subprocess.check_call(
            'yum distro-sync -y',
            shell=True,
        )
    except subprocess.CalledProcessError:
        get_logger().error(
            'Some error is occurred while synchronization of distribution.'
        )
        exit(1)
    get_logger().info(
        'Synchronization of distribution is completed successful',
    )
    set_successful_stage_status('synchronization_of_distribution')


def recreate_grub_config(grub_config_path):
    # type(str) -> None
    """
    Recreate GRUB config. Should be called after installing a new kernel
    :param grub_config_path: path to grub config
    :return: None
    """
    if get_stage_status('recreate_grub_config'):
        return
    try:
        subprocess.check_output(
            'grub2-mkconfig -o %s 2>&1' % grub_config_path,
            shell=True,
        )
    except subprocess.CalledProcessError as error:
        get_logger().error(
            'Some error is occurred while recreating '
            'grub config by path "%s".\n',
            'Please check the following output:\n'
            '%s',
            grub_config_path,
            error.output,
        )
        exit(1)
    get_logger().info(
        'The grub config is recreated by path "%s" successful',
        grub_config_path,
    )
    set_successful_stage_status('recreate_grub_config')


def get_pkgs_related_to_secure_boot():
    # type() -> dict(str, str)
    """
    Get all of Secure Boot related rpm packages
    :return: Dictionary there is key - a package, value - vendor of a package
    """
    result = {}
    pkg_prefixes = (
        'shim',
        'fwupd',
        'grub2',
        'kernel-',
    )
    try:
        output = subprocess.check_output(
            'rpm -qa --queryformat "%{name}\t%{name}-%{version}-'
            '%{release}.%{arch}\t%{vendor}\n" 2>&1',
            shell=True,
        )
        for line in output.strip().split('\n'):
            pkg_name, pkg, vendor = line.strip().split('\t')
            if any(pkg_name.startswith(pkg_prefix)
                   for pkg_prefix in pkg_prefixes):
                get_logger().info(
                    'The package "%s" relates to '
                    'Secure Boot and released by "%s"',
                    pkg,
                    vendor,
                )
                result[pkg] = vendor.lower()
    except subprocess.CalledProcessError as error:
        get_logger().error(
            'Some error is occurred while getting list '
            'of secure boot related packages.\n'
            'Please check the following output:\n'
            '%s',
            error.output,
        )
        exit(1)
    return result


def get_kernel_pkg_name_for_default_boot_record():
    # type() -> dict(str, str)
    """
    Get rpm package for default boot kernel
    :return: Dictionary there is key - a kernel package,
             value - vendor of a kernel package
    """
    try:
        kernel_path = subprocess.check_output(
            'grubby --default-kernel 2>&1',
            shell=True,
        ).strip()
        kernel_pkg_name, vendor = subprocess.check_output(
            'rpm -qf "{}" --queryformat "%{{name}}-%{{version}}-'
            '%{{release}}.%{{arch}}\t%{{vendor}}\n"'.format(kernel_path),
            shell=True,
        ).strip().split()
        get_logger().info(
            'Kernel package name "%s" is set for default '
            'boot record and released by "%s"',
            kernel_pkg_name,
            vendor,
        )
        return {kernel_pkg_name: vendor.lower()}
    except subprocess.CalledProcessError as error:
        get_logger().error(
            'Some error is occurred while getting '
            'a kernel package name for default boot record.\n'
            'Please check the following output:\n'
            '%s',
            error.output,
        )
        exit(1)


def reinstall_secure_boot_related_packages():
    # type() -> None
    """
    Reinstall all of Secure Boot related rpm
    packages if them vendor isn't CentOS
    :return: None
    """
    if get_stage_status('reinstall_secure_boot_related_packages'):
        return
    pkgs = get_pkgs_related_to_secure_boot()
    pkgs.update(get_kernel_pkg_name_for_default_boot_record())
    for pkg, vendor in pkgs.iteritems():
        if vendor == 'centos':
            continue
        try:
            get_logger().info(
                'Package "%s" is released not by '
                'CentOS and should reinstalled',
                pkg,
            )
            subprocess.check_output(
                'yum reinstall -y "%s"' % pkg,
                shell=True,
            )
        except subprocess.CalledProcessError as error:
            get_logger().error(
                'Some error is occurred while reinstalling '
                'a secure boot related package.\n'
                'Please check the following output:\n'
                '%s',
                error.output,
            )
            exit(1)
    set_successful_stage_status('reinstall_secure_boot_related_packages')


def add_boot_record_by_efibootmgr():
    # type() -> None
    """
    Add a new EFI boot record for CentOS bootloader
    :return: None
    """
    if get_stage_status('add_boot_record_by_efibootmgr'):
        return
    bootloader_path = '/EFI/centos/shimx64.efi'
    try:
        subprocess.check_output(
            'efibootmgr -c -L "CentOS Linux" -l "%s"' % bootloader_path,
            shell=True,
        )
        get_logger().info(
            'The new EFI boot record is added for bootloader "%s"',
            bootloader_path,
        )
    except subprocess.CalledProcessError as error:
        get_logger().error(
            'Some error is occurred while adding a new boot EFI record.\n'
            'Please check the following output:\n'
            '%s',
            error.output,
        )
        exit(1)
    set_successful_stage_status('add_boot_record_by_efibootmgr')


def check_and_set_default_grub_record():
    # type() -> None
    """
    Check default GRUB record using grubby and set it to default kernel if
        it's empty
    :return: None
    """
    if get_stage_status('check_and_set_default_grub_record'):
        return
    try:
        subprocess.check_call(
            'grubby --info=DEFAULT &> /dev/null',
            shell=True,
        )
        set_successful_stage_status('check_and_set_default_grub_record')
        return
    except subprocess.CalledProcessError:
        pass
    try:
        subprocess.check_output(
            'grubby --set-default=`grubby --default-kernel`',
            shell=True,
        )
        get_logger().info(
            'The default GRUB boot record is set for CentOS kernel',
        )
    except subprocess.CalledProcessError as error:
        get_logger().error(
            'Some error is occurred while set a default GRUB record.\n'
            'Please check the following output:\n'
            '%s',
            error.output,
        )
        exit(1)
    set_successful_stage_status('check_and_set_default_grub_record')


def check_supported_os():
    # type() -> None
    """
    Check that a current os is supported by this script.
    The functions checks major version and OS name.
    :return: None
    """
    if get_stage_status('check_supported_os'):
        return
    major_version, minor_version, os_name = get_os_version_and_name()
    if major_version != SUPPORTED_MAJOR_VERSION_OS:
        get_logger().info(
            'Current major version "%s" is not supported by this script.\n'
            'One is applicable only for major version "%"',
            major_version,
            SUPPORTED_MAJOR_VERSION_OS,
        )
        exit(0)
    if os_name != SUPPORTED_NAME_OS:
        get_logger().info(
            'Current OS "%s" is not supported by this script.\n'
            'One is applicable only for "%s"',
            os_name,
            SUPPORTED_NAME_OS,
        )
        exit(0)
    set_successful_stage_status('check_supported_os')


def main():
    is_conversion_completed()
    is_run_under_root()
    check_supported_os()
    remove_redhat_packages()
    remove_not_needed_dirs()
    if is_katello_satelite():
        remove_katello_satellite_packages()
    install_centos_packages()
    update_the_system()
    synchronization_of_distribution()
    if is_efi_system():
        recreate_grub_config(
            grub_config_path='/boot/efi/EFI/centos/grub.cfg'
        )
        reinstall_secure_boot_related_packages()
        add_boot_record_by_efibootmgr()
    else:
        recreate_grub_config(
            grub_config_path='/boot/grub2/grub.cfg'
        )
    check_and_set_default_grub_record()
    set_successful_stage_status('completed')
    get_logger().info('The system is migrated to CentOS 7')


if __name__ == '__main__':
    main()
