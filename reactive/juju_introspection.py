import os
import subprocess

from charms.reactive import (
    remove_state,
    set_state,
    when,
    when_not,
)

from charmhelpers.core import (
    hookenv,
    templating,
    unitdata,
)

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

    if old_port:
        hookenv.close_port(old_port)
    hookenv.open_port(new_port)


def write_systemd_unit(port):
    listen_addr = ':{}'.format(port)
    juju_introspection_hook = os.path.abspath('./scripts/agent-change')
    templating.render(
      'juju-introspection.service',
      '/etc/systemd/system/juju-introspection.service',
      {
        'addr':       listen_addr,
        'executable': os.path.join(GOPATH, 'bin', 'juju-introspection-proxy'),
        'hook':       juju_introspection_hook,
        'unit_name':  hookenv.local_unit(),
      },
    )


@when('prometheus.available')
@when('juju-introspection.agents-changed')
def agents_changed(prometheus):
    config = hookenv.config()
    port = config['port']
    
    kv = unitdata.kv()
    agents = kv.getrange('agent.', strip=True)
    for name, state in agents.items():
        # TODO(axw) the prometheus interface currently
        # assumes that a relation strand can describe
        # only one prometheus target. We should request
        # a change to the interface to support multiple.
        #
        # Alternatively, when promreg is enabled by
        # default, and can be used without additional
        # configuration, we could use that instead.
        if not name.startswith('machine-'):
            continue
        if state == 'register':
            path = '/agents/{}/metrics'.format(name)
            prometheus.configure(port, path)
            kv.set('agent.' + name, 'registered')
            break
        else:
            # TODO(axw) the prometheus interface does
            # not support deregistering a target. This
            # only matters if/when we support registering
            # unit agent targets.
            pass
    remove_state('juju-introspection.agents-changed')

