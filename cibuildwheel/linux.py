from __future__ import print_function
import os, subprocess
from .util import prepare_command

try:
    from shlex import quote as shlex_quote
except ImportError:
    from pipes import quote as shlex_quote


def build(project_dir, package_name, output_dir, test_command, test_requires, before_build):
    for docker_image in ['quay.io/pypa/manylinux1_x86_64', 'quay.io/pypa/manylinux1_i686']:
        bash_script = '''
            set -o errexit
            set -o xtrace
            cd /project

            for PYBIN in /opt/python/*/bin; do
                if [ ! -z {before_build} ]; then
                    PATH=$PYBIN:$PATH sh -c {before_build}
                fi

                "$PYBIN/pip" wheel . -w /tmp/linux_wheels
            done

            for whl in /tmp/linux_wheels/*.whl; do
                auditwheel repair "$whl" -w /output
            done

            # Install packages and test
            for PYBIN in /opt/python/*/bin/; do
                # Install the wheel we just built
                "$PYBIN/pip" install {package_name} --no-index -f /output

                # Install any requirements to run the tests
                if [ ! -z "{test_requires}" ]; then
                    "$PYBIN/pip" install {test_requires}
                fi

                # Run the tests from a different directory
                if [ ! -z {test_command} ]; then
                    pushd $HOME
                    PATH=$PYBIN:$PATH sh -c {test_command}
                    popd
                fi
            done
        '''.format(
            package_name=package_name,
            test_requires=' '.join(test_requires),
            test_command=shlex_quote(
                test_command.format(project='/project') if test_command else ''
            ),
            before_build=shlex_quote(
                prepare_command(before_build, python='python', pip='pip') if before_build else ''
            ),
        )

        docker_process = subprocess.Popen([
                'docker',
                'run',
                '--rm',
                '-i',
                '-v', '%s:/project' % os.path.abspath(project_dir),
                '-v', '%s:/output' % os.path.abspath(output_dir),
                docker_image,
                '/bin/bash'],
            stdin=subprocess.PIPE)

        docker_process.communicate(bash_script)

        if docker_process.returncode != 0:
            exit(1)
