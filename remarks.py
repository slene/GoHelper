'''
Event listener which scans content, finds special remark words like FIXME,
TODO, WARNING, INFO or DONE and highlights them.

In order to access the commands you have to add these to your key bindings:
{ "keys": ["alt+down"], "command": "highlight_code_remarks_switch",
  "args": {"direction": 1} },
{ "keys": ["alt+up"], "command": "highlight_code_remarks_switch",
  "args": {"direction": -1} },

You might want to override the following parameters within your file settings:
* highlight_code_remarks_max_file_size
  Restrict this to a sane size in order not to DDOS your editor.

Add these to your theme (and optionally adapt the colors to your liking):
        <dict>
            <key>name</key>
            <string>Remark TODO</string>
            <key>scope</key>
            <string>remark.todo</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#FFAAAA</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark DONE</string>
            <key>scope</key>
            <string>remark.done</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#AAFFAA</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark WORKING</string>
            <key>scope</key>
            <string>remark.working</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#FFFFAA</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark WAITING</string>
            <key>scope</key>
            <string>remark.waiting</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#FFFFAA55</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark NOTE</string>
            <key>scope</key>
            <string>remark.note</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#AAAAAA</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark FIXME</string>
            <key>scope</key>
            <string>remark.fixme</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#FFAAAA</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark WARNING</string>
            <key>scope</key>
            <string>remark.warning</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#FB9A4B</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark INFO</string>
            <key>scope</key>
            <string>remark.info</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#FFFFAA</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark EXCEPTION</string>
            <key>scope</key>
            <string>remark.exception</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#FFAAAA</string>
            </dict>
        </dict>
        <dict>
            <key>name</key>
            <string>Remark ERROR</string>
            <key>scope</key>
            <string>remark.error</string>
            <key>settings</key>
            <dict>
                <key>foreground</key>
                <string>#FB9A4B</string>
            </dict>
        </dict>

@author: Oktay Acikalin <ok@ryotic.de>

@license: MIT (http://www.opensource.org/licenses/mit-license.php)

@since: 2011-02-26

@TODO Add forward and backward jumping to remark words in buffer.
@TODO Add queue jumping to switch between them.
@TODO When in a line where only one region is being highlighted and the cursor
      does not touch it, try to get a region of the whole line, find the region
      in it and trigger the switch.)
'''

import sublime
import sublime_plugin


DEFAULT_MAX_FILE_SIZE = 1048576
DEFAULT_DELAY = 500

IGNORE_SYNTAX = []  # ['orgmode']

# _leading_stars = r'(?:^[ \t]*?[*]+[ \t]*)?'
# _trailing_colon = r'(?:[^\'\"\n\[\]\!\?]+?[:])?'
_leading_stars = ''
_trailing_colon = ''

REMARK_QUEUES = (
    ('Todo list',
     _leading_stars + r'\<(%s)\>' + _trailing_colon, (
        ('TODO', 'remark.todo'),
        ('WORKING', 'remark.working'),
        ('WAITING', 'remark.waiting'),
        ('DONE', 'remark.done'),
        ('CANCELED', 'remark.note'),
    )),

    ('Code remarks',
     _leading_stars + r'\<(%s)\>' + _trailing_colon, (
        ('NOTE', 'remark.note'),
        ('INFO', 'remark.info'),
        ('FIXME', 'remark.fixme'),
        ('WARNING', 'remark.warning'),
        ('EXCEPTION', 'remark.exception'),
        ('ERROR', 'remark.error'),
    )),

    ('Due date',
     _leading_stars + r'\<(%s)\>(?:\s*<[^\'\"\n\[\]\!\?]+?>|\: \[\d+-\d+-\d+( \w+)?( \d+:\d+)?\]|\: <\d+-\d+-\d+( \w+)?( \d+:\d+)?>)?', (
        ('SCHEDULED', 'remark.info'),
        ('DEADLINE', 'remark.info'),
        ('OVERDUE', 'remark.warning'),
        ('CLOSED', 'remark.note'),
    )),
)

def view_is_too_big(view, max_size_setting, default_max_size=None):
    settings = view.settings()
    max_size = settings.get(max_size_setting, default_max_size)
    # print max_size, type(max_size)
    if max_size not in (None, False):
        # max_size = long(max_size)
        cur_size = view.size()
        if cur_size > max_size:
            return True
    return False


def view_is_widget(view):
    settings = view.settings()
    return bool(settings.get('is_widget'))


class DeferedViewListener(sublime_plugin.EventListener):

    def __init__(self):
        super(DeferedViewListener, self).__init__()
        self.seen_views = []
        self.max_size_setting = ''
        self.default_max_file_size = None
        self.delay = 500

    def is_enabled(self, view):
        return True
    
    def view_is_too_big_callback(self):
        pass
    
    def update(self, view):
        pass

    def defered_update(self, view):
        if not view.window():  # If view is not visible window() will be None.
            return

        if view.id() not in self.seen_views:
            self.seen_views.append(view.id())

        if view_is_widget(view):
            return
        
        if not self.is_enabled(view):
            return

        if view_is_too_big(view, self.max_size_setting,
                           self.default_max_file_size):
            self.view_is_too_big_callback(view)
            return
        
        def func():
            self.update(view)
        
        if self.delay:
            sublime.set_timeout(func, self.delay)
        else:
            func()

    def on_modified(self, view):
        '''
        Event callback to react on modification of the document.

        @type  view: sublime.View
        @param view: View to work with.

        @return: None
        '''
        self.defered_update(view)

    def on_load(self, view):
        '''
        Event callback to react on loading of the document.

        @type  view: sublime.View
        @param view: View to work with.

        @return: None
        '''
        self.defered_update(view)

    def on_activated(self, view):
        '''
        Event callback to react on activation of the document.

        @type  view: sublime.View
        @param view: View to work with.

        @return: None
        '''
        if view.id() not in self.seen_views:
            self.defered_update(view)

def get_cache():
    cache = dict()
    for title, pattern, mapping in REMARK_QUEUES:
        keys = [key for key, val in mapping]
        values = [val for key, val in mapping]
        regex = pattern % '|'.join(keys)
        regex = '(?:' + regex + ')'
        cache[title] = dict(
            pattern=pattern,
            mapping=mapping,
            keys=keys,
            values=values,
            regex=regex,
        )
    return cache

if 'found_regions' not in globals():
    found_regions = dict()


class HighlightCodeRemarksListener(DeferedViewListener):

    def __init__(self):
        super(HighlightCodeRemarksListener, self).__init__()
        self.cache = get_cache()
        self.max_size_setting = 'highlight_code_remarks_max_file_size'
        self.default_max_file_size = DEFAULT_MAX_FILE_SIZE
        self.delay = DEFAULT_DELAY

    def is_enabled(self, view):
        view_syntax = view.settings().get('syntax')
        for syntax in IGNORE_SYNTAX:
            if syntax in view_syntax:
                return False
        return True

    def view_is_too_big_callback(self, view):
        for title, queue in self.cache.items():
            for color_value in queue['values']:
                tag = 'HighlightCodeRemarksListener.%s.%s' % (title,
                                                              color_value)
                view.erase_regions(tag)

    def update_queue(self, view, title, queue):
        buffer_id = view.buffer_id()
        remarks = []
        regions = view.find_all(queue['regex'], sublime.OP_REGEX_MATCH,
                                '$0', remarks)
        results = dict()
        for pos, region in enumerate(regions):
            remark = remarks[pos]
            remark = remark.strip('\t :*')
            # print pos, region, remark
            color_value = False
            color_key = False
            for key, val in queue['mapping']:
                # print key, val, remark
                if remark.startswith(key):
                    color_value = val
                    color_key = key
                    break
            if not color_value:
                continue
            # print color_value
            if color_value not in results:
                results[color_value] = list()
            results[color_value].append(region)
            found_regions[buffer_id].append((title, color_key, color_value, region))
        # print results
        for color_value in queue['values']:
            tag = 'HighlightCodeRemarksListener.%s.%s' % (title, color_value)
            if color_value in results:
                # print('add', tag, results[color_value], color_value)
                view.add_regions(tag, results[color_value], color_value, "", sublime.DRAW_EMPTY)
            else:
                # print 'remove', tag
                view.erase_regions(tag)

    def update(self, view):
        buffer_id = view.buffer_id()
        found_regions[buffer_id] = list()
        for title, queue in self.cache.items():
            self.update_queue(view, title, queue)


class HighlightCodeRemarksSwitchCommand(sublime_plugin.TextCommand):

    def __init__(self, view):
        super(HighlightCodeRemarksSwitchCommand, self).__init__(view)
        self.cache = get_cache()

    def find_region_for_sel(self, sel, regions):
        for item in regions:
            title, key, value, region = item
            if region.contains(sel):
                return item
        return None

    def run(self, edit, direction=1):
        buffer_id = self.view.buffer_id()
        sels = self.view.sel()
        if len(sels) == 1:
            sel = sels[0]
            regions = found_regions[buffer_id]
            sel_region = self.find_region_for_sel(sel, regions)
            if sel_region is None:
                return  # Nothing found.
            # print sel_region
            title, key, value, region = sel_region
            keys = self.cache[title]['keys']
            sel = self.view.find(key, region.begin(), sublime.LITERAL)
            if not sel:
                print(title, key, value, region)
                sublime.error_message('Could not switch remark for: %s' % title)
                return
            sublime.status_message('Switching within remark queue: %s' % title)
            pos = keys.index(key)
            pos += int(direction)
            if pos >= len(keys):
                pos = 0
            elif pos < 0:
                pos = len(keys) - 1
            self.view.replace(edit, sel, keys[pos])
            # Remove obsolete regions.
            tag = 'HighlightCodeRemarksListener.%s.%s' % (title, value)
            self.view.erase_regions(tag)
            for region in regions[:]:
                if region[0] == title:
                    regions.remove(region)