import os
import subprocess

from charms.reactive import when, when_not, set_state
from charmhelpers.core import hookenv, templating

GOPATH = os.path.abspath('./gopath')

@when_not('juju-introspection.installed')
def install_juju_introspection():

    # Build/install the proxy application.
    new_env = os.environ.copy()
    if not os.path.exists(GOPATH):
      os.makedirs(GOPATH, 0o755)
    new_env['GOPATH'] = GOPATH
    subprocess.check_call(
      ['go', 'get', 'github.com/axw/juju-introspection-proxy'],
      env=new_env,
    )

    # Create a systemd unit file, and open the port.
    port = hookenv.config()['port']
    write_systemd_unit(port)
    subprocess.check_call(['systemctl', 'enable', 'juju-introspection'])
    subprocess.check_call(['systemctl', 'start', 'juju-introspection'])
    hookenv.open_port(port)
    set_state('juju-introspection.installed')


@when('config.changed.port')
def update_systemd_unit():
    config = hookenv.config()
    new_port = config['port']
    old_port = config.previous('port')

    write_systemd_unit(new_port)
    subprocess.check_call(['systemctl', 'daemon-reload'])
    subprocess.check_call(['systemctl', 'restart', 'juju-introspection'])

    hookenv.close_port(old_port)
    hookenv.open_port(new_port)


def write_systemd_unit(port):
    listen_addr = ':{}'.format(port)
    juju_introspection_hook = os.path.abspath('./scripts/agent-change')
    templating.render(
      'juju-introspection.service',
      '/etc/systemd/system/juju-introspection.service',
      {
        'executable': os.path.join(GOPATH, 'bin', 'juju-introspection-proxy'),
        'addr': listen_addr,
        'hook': juju_introspection_hook,
      },
    )

