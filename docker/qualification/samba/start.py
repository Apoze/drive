"""Disposable SMB qualification server; credentials exist only in a mounted secret."""
import json
import os
import pathlib
import subprocess

credentials = json.loads(pathlib.Path('/run/secrets/qualification').read_text())
for user, password in credentials.items():
    subprocess.run(['useradd', '-M', '-s', '/usr/sbin/nologin', user], check=True)
    subprocess.run(['smbpasswd', '-s', '-a', user], input=f'{password}\n{password}\n',
                   text=True, stdout=subprocess.DEVNULL, check=True)
root = pathlib.Path('/srv/data')
for name in ('alice', 'bob'):
    (root / name).mkdir(parents=True, exist_ok=True)
(root / 'alice' / 'hello.txt').write_text('hello')
(root / 'bob' / 'private.txt').write_text('private')
(root / 'alice' / 'escape').symlink_to('../bob', target_is_directory=True)
pathlib.Path('/etc/samba/smb.conf').write_text('''[global]
server role = standalone server
server min protocol = SMB3
map to guest = Never
load printers = no
printing = bsd
printcap name = /dev/null
log level = 0
[nas]
path = /srv/data
read only = no
valid users = qa-a qa-b
force user = root
follow symlinks = yes
wide links = no
[only-a]
path = /srv/data/alice
read only = no
valid users = qa-a
force user = root
[only-b]
path = /srv/data/bob
read only = no
valid users = qa-b
force user = root
''')
os.execvp('smbd', ['smbd', '--foreground', '--no-process-group', '--debug-stdout'])
