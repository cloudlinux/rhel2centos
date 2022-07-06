# RHEL 7 to CentOS 7 migration tool

## Usage

In order to convert your RHEL 7 operating system to CentOS 7 do the following:

1. Make a backup of the system. We didn't test all possible scenarios so there
   is a risk that something goes wrong. In such a situation you will have a
   restore point.
2. Download the [migrate_7.py](migrate_7.py) script:
   ```shell
   curl -O https://raw.githubusercontent.com/nstankov-bg/rhel2centos/main/migrate_7.py
   ```
3. Run the script and check its output for errors:
   ```shell
   sudo python migrate_7.py
   ```
4. Ensure that your system was successfully converted:
   ```shell
   ##check release file
   cat /etc/redhat-release
   ```
   ```
   ##check that the system boots CentOS kernel by default
   sudo grubby --info DEFAULT | grep CentOS
   ##title=CentOS Linux (3.10.0-1160.31.1.el7.x86_64) 7 (Core)
   ```

## License

Licensed under the GPLv3 license, see the [LICENSE](LICENSE) file for details.
