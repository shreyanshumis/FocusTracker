"""Native UI lifecycle test using temporary settings and hosts; never real rules."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tempfile
import time
import tkinter as tk
from unittest.mock import patch, Mock
from core import HostsFile
from main import App

def pump(root, seconds=.3):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        root.update()
        time.sleep(.01)

with tempfile.TemporaryDirectory() as folder, patch.object(App, 'start_tray'):
    base = Path(folder)
    hosts = base / 'hosts'
    original = b'127.0.0.1 localhost\r\n'
    hosts.write_bytes(original)
    root = tk.Tk()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    signals = Mock()
    signals.pending.return_value = []
    app = App(root, base / 'settings.json', HostsFile(hosts, base / 'backup'), demo=True, signals=signals)
    pump(root)
    root.withdraw()
    signals.pending.return_value = ['show']
    pump(root, .6)
    signals.pending.return_value = []
    assert root.state() == 'normal', 'Opening a running app must restore its window'
    assert app.config['domains'] == [], 'Fresh installs must have no websites'
    app.show_page('Websites')
    app.site_input.set('https://www.reddit.com/r/study/')
    app.add_domain()
    assert app.config['domains'] == ['reddit.com']
    app.site_input.set('www.reddit.com')
    app.add_domain()
    assert app.config['domains'] == ['reddit.com'], 'Equivalent addresses must not duplicate'
    app.show_page('Overview')
    app.duration.set('37')
    app.start_timer(True)
    pump(root, .8)
    assert app.duration.get() == '37'
    assert app.config['timer']['block']
    assert b'reddit.com' in hosts.read_bytes()
    # Destroy pages during pending hover/progress/page animations.
    for page in ['Websites', 'Schedules', 'How it works', 'Overview'] * 3:
        app.nav[page].event_generate('<Enter>')
        app.show_page(page)
        pump(root, .025)
    pump(root)
    assert app.duration.get() == '37', 'Duration must survive navigation'
    app.reduced_motion.set(True)
    app.save_motion()
    app.show_page('Websites')
    assert app.motion_job is None
    with patch('main.messagebox.askyesno', return_value=True):
        app.remove_all_domains()
    pump(root, .8)
    assert app.config['domains'] == []
    assert hosts.read_bytes() == original, 'Clearing the list must restore access'
    app.show_page('Overview')
    # Exit while an update is pending; cleanup must run last, without blocking Tk.
    app.apply_async(['example.com'], ('example.com',))
    signals.pending.return_value = ['quit']
    end = time.monotonic() + 5
    while not app.closed and time.monotonic() < end:
        root.update()
        time.sleep(.01)
    assert app.closed, 'Shutdown did not complete'
    assert hosts.read_bytes() == original, 'Exit must remove app rules'
    assert not errors, errors
    print('PASS: native pages, animations, preferences, timer persistence, async exit cleanup')
