import os
import re
import time
import json
import subprocess

import sublime
import sublime_plugin

stash = {}


def sel(view, i=0):
	try:
		s = view.sel()
		if s is not None and i < len(s):
			return s[i]
	except Exception:
		pass
	return sublime.Region(0, 0)

def is_go_source_view(view=None, strict=True):
	if view is None:
		return False

	selector_match = view.score_selector(sel(view).begin(), 'source.go') > 0
	if selector_match:
		return True

	if strict:
		return False

	fn = view.file_name() or ''
	return fn.lower().endswith('.go')

def is_go_test_view(view=None, strict=True):
	if view is None:
		return False

	if not is_go_source_view(view, strict):
		return False

	fn = view.file_name() or ''
	return fn.lower().endswith('_test.go') and fn.lower() != '_test.go'

def active_valid_go_view(win=None, strict=True):
	if not win:
		win = sublime.active_window()
	if win:
		view = win.active_view()
		if view and is_go_source_view(view, strict):
			return view
	return None

def get_goenv(setting = None):
	from GoSublime.gs9o import active_wd

	if not setting:
		setting = get_setting()
	senv = setting.get('env', {})

	wd = active_wd()

	gopath = [os.path.normpath(p) for p in os.environ.get('GOPATH', '').split(os.path.pathsep) if p]

	gsPath = senv.get('GOPATH', '')
	if gsPath.find('$GS_GOPATH') != -1:
		p = wd + os.path.sep
		i = p.find(os.path.sep + "src" + os.path.sep)
		if i != -1:
			gsPath = gsPath.replace('$GS_GOPATH', wd[:i])

	_p = gopath
	gopath = [os.path.normpath(p) for p in gsPath.split(os.path.pathsep)]
	gopath.extend(_p)

	GOPATH = []
	for p in gopath:
		if p and p != '.' and p not in GOPATH:
			GOPATH.append(p)

	env = os.environ.copy()
	env['GOPATH'] = os.path.pathsep.join(GOPATH)
	goos = senv.get('GOOS')
	goarch = senv.get('GOARCH')
	if goos: env['GOOS'] = goos.lower()
	if goarch: env['GOARCH'] = goarch.lower()

	return env

def get_setting():
	return sublime.load_settings("GoSublime.sublime-settings")

def save_settings():
	sublime.save_settings("GoSublime.sublime-settings")

bingo = 0
class EVT(sublime_plugin.EventListener):
	def on(self):
		global bingo
		bingo += 1
	def off(self):
		global bingo
		bingo = 0
	def on_post_save(self, view, *args, **kwargs):
		self.on()
		if bingo > 1:
			self.off()
			GoInstallCommand(view.window()).run(save = False)
	def on_new(self, *args, **kwargs):
		self.off()
	def on_clone(self, *args, **kwargs):
		self.off()
	def on_load(self, *args, **kwargs):
		self.off()
	def on_close(self, *args, **kwargs):
		self.off()
	def on_modified(self, *args, **kwargs):
		self.off()
	def on_selection_modified(self, *args, **kwargs):
		self.off()
	def on_activated(self, *args, **kwargs):
		self.off()
	def on_deactivated(self, *args, **kwargs):
		self.off()
	def on_text_command(self, view, cmd, *args, **kwargs):
		if cmd == "gs_fmt_save":
			return
		self.off()
	def on_window_command(self, *args, **kwargs):
		pass

class GoInstallCommand(sublime_plugin.WindowCommand):
	panel_name = 'output.GoInstall-output'
	reg_lines = re.compile(r'^(?P<file>[^ ]+\.go):(?P<line>\d+):.*', re.I|re.M)

	def run(self, save = True):
		view = self.window.active_view()

		if save:
			view.run_command("save")

		if active_valid_go_view(self.window) is None:
			return

		from GoSublime.gosubl import gs, mg9

		env = get_goenv()

		cmd = 'install'
		if is_go_test_view(view):
			cmd = 'test'

		a = {
			'cid': '9go-%s' % wd,
			'env': env,
			'cwd': wd,
			'cmd': {
				'name': 'go',
				'args': [cmd],
			}
		}

		win = sublime.active_window()
		panel = stash.get(self.panel_name)
		if not panel:
			panel = stash[self.panel_name] = win.get_output_panel(self.panel_name)

		def focus(out):
			lines = self.reg_lines.findall(out)
			if len(lines) > 0:
				f, n = lines[0]
				from os import path
				if not path.isabs(f):
					f = path.join(wd, f)
					sublime.set_timeout(lambda: win.open_file('%s:%s' % (f, n), sublime.ENCODED_POSITION), 0)

		def cb(res, err):
			out = res.get('err', '').strip()
			if out:
				gs.show_output('GoInstall', out, False, gs.tm_path('go'))
				focus(out)
			else:
				if panel is not None:
					sublime.set_timeout(lambda: win.run_command('hide_panel'), 0)
		sublime.set_timeout(lambda: mg9.acall('sh', a, cb), 0)

GO_OS_ARCH = [
	['darwin', '386'],
	['darwin', 'amd64'],
	['linux', '386'],
	['linux', 'amd64'],
	['linux', 'arm'],
	['windows', '386'],
	['windows', 'amd64'],
	['freebsd', '386'],
	['freebsd', 'amd64'],
	['netbsd', '386'],
	['netbsd', 'amd64'],
	['openbsd', '386'],
	['openbsd', 'amd64'],
	['plan9', '386'],
]

def current_os_arch_index():
	env = get_goenv()
	goos = env.get("GOOS", '').lower()
	goarch = env.get("GOARCH", '').lower()
	for i, d in enumerate(GO_OS_ARCH):
		o, a = d
		if goos == o and goarch == a:
			return i
	return -1

def change_os_arch(index):
	if index > -1 and index < len(GO_OS_ARCH) and index != current_os_arch_index():
		goos, goarch = GO_OS_ARCH[index]
		setting = get_setting()
		env = get_goenv(setting)
		env['GOOS'] = goos
		env['GOARCH'] = goarch
		setting.set('env', env)
		save_settings()

class GoSelectOsArchCommand(sublime_plugin.WindowCommand):
	def run(self):
		i = current_os_arch_index()
		result = ['%s - %s' % (os, arch) for os, arch in GO_OS_ARCH]
		if i != -1:
			result[i] = result[i] + ' (current)'
		self.window.show_quick_panel(result, self.on_done)

	def on_done(self, index):
		change_os_arch(index)

class GoChangeOsArchCommand(sublime_plugin.ApplicationCommand):
	def is_checked(self, index):
		goos, goarch = GO_OS_ARCH[index]
		senv = get_goenv()
		return senv.get("GOOS", '').lower() == goos and senv.get("GOARCH", '').lower() == goarch

	def run(self, index):
		change_os_arch(index)

class GohelperGodefCommand(sublime_plugin.WindowCommand):
	def run(self):
		print("=================[Godef] Start =================")

		setting = get_setting()
		godef_path = setting.get('godef_path', '')
		env = get_goenv(setting)

		if not godef_path:
			paths = env.get('GOPATH', '').split(':')
			for path in paths:
				test_path = os.path.join(path, 'bin', 'godef')
				if not os.path.isfile(test_path):
					continue
				print("[Godef]INFO: godef found at" + test_path)
				godef_path = test_path

			if godef_path:
				setting.set('godef_path', godef_path)
				print('godef save')
				save_settings()

		if not os.path.isfile(godef_path):
			print('[Godef]ERROR: godef not found')
			return

		view = self.window.active_view()
		select = view.sel()[0]
		select_begin = select.begin()
		select_before = sublime.Region(0, select_begin)
		string_before = view.substr(select_before)
		string_before.encode("utf-8")
		buffer_before = bytearray(string_before, encoding = "utf8")
		offset = len(buffer_before)
		print("[Godef]INFO: selcet_begin: " + str(select_begin) + " offset: " + str(offset))

		filename = view.file_name()

		args = [
			godef_path,
			"-f",
			filename,
			"-o",
			str(offset)
		]

		print("[Godef]INFO: spawning: " + " ".join(args))

		p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
		output, stderr = p.communicate()
		if stderr:
			print("[Godef]ERROR: no definition found: " + str(stderr))
			print("=================[Godef] End =================")
			return

		location = output.decode("utf-8").rstrip().split(":")

		if len(location) == 3:
			print("[Godef]INFO: godef output: " + str(output))
			file = location[0]
			row = int(location[1])
			col = int(location[2])

			postion = (file + ":" + str(row) + ":" + str(col))
			print("[Godef]INFO: opening definition at " + postion)
			view = self.window.open_file(postion, sublime.ENCODED_POSITION)
			# view.show_at_center(region)
		else:
			print("[Godef]ERROR: godef output bad: " + str(output))
		print("=================[Godef] End =================")
