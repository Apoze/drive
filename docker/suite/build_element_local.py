"""Build Element with a dedicated, memory-limited native BuildKit worker."""

import argparse
import json
from pathlib import Path
import subprocess

BUILDER = 'apoze-suite'
IMAGE = 'moby/buildkit:v0.33.0@sha256:6c2fa84a6b61ccd72899dde4239f8d5717f05f9a8ca6f3cad185fb1a95a94de3'
LIMIT = 2560 * 1024**2


def build(repo, *, check=False):
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    if available < LIMIT + 512 * 1024**2:
        raise RuntimeError('Not enough free build capacity: need 3 GiB available; preserve running business services')
    found = subprocess.run(['docker', 'buildx', 'inspect', BUILDER], capture_output=True)
    if found.returncode:
        subprocess.run(['docker', 'buildx', 'create', '--name', BUILDER, '--driver', 'docker-container',
                        '--driver-opt', 'image=' + IMAGE, '--driver-opt', 'memory=2560m',
                        '--driver-opt', 'memory-swap=2560m', '--driver-opt', 'cpu-period=100000',
                        '--driver-opt', 'cpu-quota=200000'], check=True)
    subprocess.run(['docker', 'buildx', 'inspect', '--bootstrap', BUILDER], check=True)
    runtime = json.loads(subprocess.check_output(['docker', 'inspect', 'buildx_buildkit_' + BUILDER + '0']))[0]
    limits = runtime['HostConfig']
    if limits['Memory'] != LIMIT or limits['MemorySwap'] != LIMIT or limits['CpuQuota'] != 200000 or limits['CpuPeriod'] != 100000:
        raise RuntimeError('Existing suite builder has different resource limits; do not use it implicitly')
    if runtime['Config']['Image'] != IMAGE:
        raise RuntimeError('Existing suite builder image differs from the pinned version')
    if check:
        print('Native BuildKit worker verified: 2.5 GiB total, no swap, two CPUs')
        return
    try:
        subprocess.run(['docker', 'buildx', 'build', '--builder', BUILDER, '--load', '--target', 'element_web',
                        '--file', str(repo / 'apps/web/Dockerfile'), '--tag', 'apoze/element-web:suite-local', str(repo)], check=True)
        peak = subprocess.check_output(['docker', 'exec', 'buildx_buildkit_' + BUILDER + '0',
                                        'cat', '/sys/fs/cgroup/memory.peak'], text=True).strip()
        print('Native build memory peak: ' + str(round(int(peak) / 1024**2)) + ' MiB')
    finally:
        subprocess.run(['docker', 'buildx', 'stop', BUILDER], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3] / 'element-web')
    parser.add_argument('--check', action='store_true', help='Verify the real builder without compiling')
    args = parser.parse_args()
    build(args.repo.resolve(), check=args.check)
