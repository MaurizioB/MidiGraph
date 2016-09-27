#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

import sys
from os import path
from copy import copy
from PyQt4 import QtCore, QtGui, uic
from midiutils import *

_path = path.dirname(path.abspath(__file__))
def _load_ui(widget, ui_path):
    return uic.loadUi(path.join(_path, ui_path), widget)

def _get_key(d, value):
    return d.keys()[d.values().index(value)]

def setBold(item, bold=True):
    font = item.font()
    font.setBold(bold)
    item.setFont(font)

UserRole = QtCore.Qt.UserRole
IdRole = UserRole + 1
ClientRole = UserRole + 2
PortRole = UserRole + 3
VisibleRole = UserRole + 4

def client_icon(client):
    if client.type == alsaseq.SEQ_USER_CLIENT:
        return QtGui.QIcon(path.join(_path, 'speaker.svg'))
    else:
        return QtGui.QIcon(path.join(_path, 'circuit.svg'))

port_type_checks = [
                    ('PORT', ), 
                    ('HARDWARE', 'SOFTWARE', 'APPLICATION'), 
                    ('MIDI_GENERIC', 'MIDI_GM', 'MIDI_GM2'), 
                    ('MIDI_GS', 'MIDI_MT32', 'MIDI_XG'), 
                    ('SYNTHESIZER', 'SAMPLE', 'DIRECT_SAMPLE'), 
                    ('SPECIFIC', 'SYNTH'), 
                    ]
port_type_to_str = {bit:str(value)[14:] for bit, value in alsaseq._dporttype.items()}
port_type_tooltip = {
                     'PORT': 'This port may connect to other devices (whose characteristics are not known).', 
                     'HARDWARE': 'This port is implemented in hardware.', 
                     'SOFTWARE': 'This port is implemented in software.', 
                     'APPLICATION': 'This port belongs to an application, such as a sequencer or editor.', 
                     'MIDI_GENERIC': 'This port understands MIDI messages.', 
                     'MIDI_GM': 'This port is compatible with the General MIDI specification.', 
                     'MIDI_GM2': 'This port is compatible with the General MIDI 2 specification.', 
                     'MIDI_GS': 'This port is compatible with the Roland GS standard.', 
                     'MIDI_MT32': 'This port is compatible with the Roland MT-32.', 
                     'MIDI_XG': 'This port is compatible with the Yamaha XG specification.', 
                     'SYNTHESIZER': 'Messages sent to this port will generate sounds.', 
                     'SAMPLE': 'Instruments can be downloaded to this port (with SND_SEQ_EVENT_INSTR_xxx messages sent directly or through a queue).', 
                     'DIRECT_SAMPLE': 'Instruments can be downloaded to this port (with SND_SEQ_EVENT_INSTR_xxx messages sent directly).', 
                     'SPECIFIC': 'Messages sent from/to this port have device-specific semantics.', 
                     'SYNTH': 'This port understands SND_SEQ_EVENT_SAMPLE_xxx messages (these are not MIDI messages).', 
                     }

port_cap_checks = [
                   ('DUPLEX', 'NO_EXPORT'),
                   ('READ', 'SUBS_READ', 'SYNC_READ'), 
                   ('WRITE', 'SUBS_WRITE', 'SYNC_WRITE'), 
                   ]
port_cap_to_str = {bit:str(value)[13:] for bit, value in alsaseq._dportcap.items()}
port_cap_tooltip = {
                    'DUPLEX': 'This port is both for output and input (allow read/write).', 
                    'NO_EXPORT': 'This port does not allow routing.', 
                    'READ': 'This is an output port (readable from this port).', 
                    'SUBS_READ': 'This port will notify connections (allow read subscriptions).', 
                    'SYNC_READ': 'This port will notify connections (allow read subscriptions).', 
                    'WRITE': 'This in an input port (writable to this port).', 
                    'SUBS_WRITE': 'This port can receive connection notifications (allow write subscriptions).', 
                    'SYNC_WRITE': 'This port can receive connection notifications (allow write subscriptions).', 
                    }

class AlsaMidi(QtCore.QObject):
    client_start = QtCore.pyqtSignal(object)
    client_exit = QtCore.pyqtSignal(object)
    port_start = QtCore.pyqtSignal(object)
    port_exit = QtCore.pyqtSignal(object)
    conn_register = QtCore.pyqtSignal(object, bool)
    graph_changed = QtCore.pyqtSignal()
    stopped = QtCore.pyqtSignal()
    midi_signal = QtCore.pyqtSignal(object)

    def __init__(self, main):
        QtCore.QObject.__init__(self)
        self.main = main
        self.active = False
        self.seq = alsaseq.Sequencer(clientname='MidiPortGraph')
        self.keep_going = True
        input_id = self.seq.create_simple_port(name = 'Monitor', 
                                                     type = alsaseq.SEQ_PORT_TYPE_MIDI_GENERIC|alsaseq.SEQ_PORT_TYPE_APPLICATION, 
                                                     caps = alsaseq.SEQ_PORT_CAP_WRITE|alsaseq.SEQ_PORT_CAP_SUBS_WRITE|
                                                     alsaseq.SEQ_PORT_CAP_NO_EXPORT)
        self.seq.connect_ports((alsaseq.SEQ_CLIENT_SYSTEM, alsaseq.SEQ_PORT_SYSTEM_ANNOUNCE), (self.seq.client_id, input_id))

        self.main.graph = Graph(self.seq)
        self.graph = self.main.graph
        self.graph.client_start.connect(self.client_start)
        self.graph.client_exit.connect(self.client_exit)
        self.graph.port_start.connect(self.port_start)
        self.graph.port_exit.connect(self.port_exit)
        self.graph.conn_register.connect(self.conn_register)
        self.id = self.seq.get_client_info()['id']
        self.input = self.graph.port_id_dict[self.id][input_id]

    def run(self):
        self.active = True
        while self.keep_going:
            try:
                event_list = self.seq.receive_events(timeout=1024, maxevents=1)
                for event in event_list:
                    data = event.get_data()
                    if event.type == alsaseq.SEQ_EVENT_CLIENT_START:
                        self.graph.client_created(data)
                    elif event.type == alsaseq.SEQ_EVENT_CLIENT_EXIT:
                        self.graph.client_destroyed(data)
                    elif event.type == alsaseq.SEQ_EVENT_PORT_START:
                        self.graph.port_created(data)
                    elif event.type == alsaseq.SEQ_EVENT_PORT_EXIT:
                        self.graph.port_destroyed(data)
                    elif event.type == alsaseq.SEQ_EVENT_PORT_SUBSCRIBED:
                        self.graph.conn_created(data)
                    elif event.type == alsaseq.SEQ_EVENT_PORT_UNSUBSCRIBED:
                        self.graph.conn_destroyed(data)
            except:
                pass
        print 'stopped'
        self.stopped.emit()

class ConnectionWidget(QtGui.QWidget):
    def __init__(self, parent):
        QtGui.QWidget.__init__(self, parent)
        self.main = parent
        self.output_items = parent.output_items
        self.input_items = parent.input_items
        self.output_client_items = parent.output_client_items
        self.input_client_items = parent.input_client_items
        self.output_tree = parent.output_tree
        self.input_tree = parent.input_tree
        self.output_model = parent.output_model
        self.input_model = parent.input_model
        self.connections = set([conn for port in self.output_items for conn in port.connections.output])
        for conn in self.connections:
            conn.lost.connect(self.conn_destroyed)
        for i in range(self.output_model.rowCount()):
            if not self.output_tree.isRowHidden(i, self.output_tree.rootIndex()):
                index = self.output_model.indexFromItem(self.output_model.item(i))
                delta = self.output_tree.visualRect(index).height()/2
                break
        self.base_pos = QtCore.QPoint(0, delta)

    def append(self, conn):
        self.connections.add(conn)
        conn.lost.connect(self.conn_destroyed)
        self.update()

    def conn_destroyed(self):
        conn = self.sender()
        self.connections.discard(conn)
        self.update()

    def paintEvent(self, event):
        qp = QtGui.QPainter()
        qp.begin(self)
        qp.setRenderHints(QtGui.QPainter.Antialiasing)
        self.drawConn(event, qp)
        qp.end()

    def drawConn(self, event, qp):
        for conn in self.connections:
            src = self.output_items[conn.src]
            client_src = self.output_client_items[conn.src.client]
            dest = self.input_items[conn.dest]
            client_dest = self.input_client_items[conn.dest.client]
            if not all([i.data(VisibleRole).toPyObject() for i in [client_src, client_dest, src, dest]]): continue
            if conn in self.main.highlight_conn:
                pen = QtGui.QPen(QtCore.Qt.red)
                qp.setPen(pen)
            elif conn.src.addr[0] == 0:
                pen = QtGui.QPen(QtCore.Qt.darkRed)
                qp.setPen(pen)
            elif conn.hidden:
                pen = QtGui.QPen(QtCore.Qt.darkGray)
                qp.setPen(pen)
            else:
                pen = QtGui.QPen(QtCore.Qt.darkGreen)
                qp.setPen(pen)
            src_index = self.output_model.indexFromItem(src)
            if not self.output_tree.isExpanded(src_index.parent()):
                src_index = src_index.parent()
            dest_index = self.input_model.indexFromItem(dest)
            if not self.input_tree.isExpanded(dest_index.parent()):
                dest_index = dest_index.parent()
            src_vpos = self.output_tree.viewport().mapToParent(self.output_tree.visualRect(src_index).topLeft())+self.base_pos
            dest_vpos = self.input_tree.viewport().mapToParent(self.input_tree.visualRect(dest_index).topLeft())+self.base_pos
#            qp.drawLine(5, src_vpos.y()+self.base_pos, self.width()-5, dest_vpos.y()+self.base_pos)
            path = QtGui.QPainterPath()
            path.moveTo(5, src_vpos.y())
            delta = self.width()/1.5
            path.cubicTo(delta, src_vpos.y(), self.width()-delta, dest_vpos.y(), self.width()-5, dest_vpos.y())
            qp.drawPath(path)

class CheckLabel(QtGui.QLabel):
    toggled = QtCore.pyqtSignal(bool)
    def __init__(self, text='', parent=None, state=True):
        QtGui.QLabel.__init__(self, parent=parent)
        self._text = text
        self._state = state
        self.setTextFormat(QtCore.Qt.RichText)
        self.setText(text)
        self.linkActivated.connect(self.toggle)
        self.linkHovered.connect(self.set_cursor)
        self.setContextMenuPolicy(0)

    def set_cursor(self, url):
        self.setCursor(QtCore.Qt.ArrowCursor)

    def setText(self, text):
        QtGui.QLabel.setText(self, '<a href=".">{}</a>'.format(text))

    def setChecked(self, state):
        if state != self._state:
            self._state = state
            self.toggled.emit(self._state)

    def toggle(self):
        self._state = not self._state
        self.toggled.emit(self._state)

class IdItem(QtGui.QStyledItemDelegate):
    def __init__(self, *args, **kwargs):
        QtGui.QStyledItemDelegate.__init__(self, *args, **kwargs)

    def paint(self, qp, style, index):
        id = index.data(IdRole).toString()
        options = QtGui.QStyleOptionViewItemV4()
        options.__init__(style)
        QtGui.QStyledItemDelegate.initStyleOption(self, options, index)
        options.decorationAlignment = QtCore.Qt.AlignLeft
        qp.save()
        doc = QtGui.QTextDocument()
        doc.setHtml('<font color="gray">{}</font>'.format(id))
        max_width = QtGui.QFontMetrics(doc.defaultFont()).width(id)
        
        if not options.features & QtGui.QStyleOptionViewItemV4.HasDecoration:
            options.features = options.features|QtGui.QStyleOptionViewItemV4.HasDecoration
            options.decorationSize.setWidth(max_width)
            options.widget.style().drawControl(QtGui.QStyle.CE_ItemViewItem, options, qp)
            qp.translate(options.rect.x(), options.rect.top())
        else:
            options.decorationSize.setWidth(options.decorationSize.width()+max_width)
            options.widget.style().drawControl(QtGui.QStyle.CE_ItemViewItem, options, qp)
            qp.translate(options.rect.x()+options.decorationSize.width()-max_width, options.rect.top())
        rect = QtCore.QRectF(0, 0, options.rect.width(), options.rect.height())
        doc.drawContents(qp, rect)
        qp.restore()

    def sizeHint(self, style, index):
        options = QtGui.QStyleOptionViewItemV4()
        options.__init__(style)
        QtGui.QStyledItemDelegate.initStyleOption(self, options, index)
        doc = QtGui.QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width())
        size = QtCore.QSize()
        QtCore.QSize.__init__(size, doc.idealWidth(), doc.size().height())
        return size


class PortGraph(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        _load_ui(self, 'portgraph.ui')

        self.output_tree = QtGui.QTreeView(self)
        self.output_tree.setVerticalScrollMode(QtGui.QTreeView.ScrollPerPixel)
        self.output_tree.setAlternatingRowColors(True)
        self.output_tree.setEditTriggers(QtGui.QTreeView.NoEditTriggers)
        self.output_tree.setMouseTracking(True)
        self.output_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.output_tree.customContextMenuRequested.connect(self.tree_menu)
        self.output_tree.setItemDelegate(IdItem())
        self.output_tree.mouseMoveEvent = lambda e: self.tree_mouseMove(self.output_tree, e)
        self.output_tree.leaveEvent = lambda e: self.tree_leaveEvent(self.output_tree, e)

        self.input_tree = QtGui.QTreeView(self)
        self.input_tree.setVerticalScrollMode(QtGui.QTreeView.ScrollPerPixel)
        self.input_tree.setAlternatingRowColors(True)
        self.input_tree.setEditTriggers(QtGui.QTreeView.NoEditTriggers)
        self.input_tree.setMouseTracking(True)
        self.input_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.input_tree.customContextMenuRequested.connect(self.tree_menu)
        self.input_tree.setItemDelegate(IdItem())
        self.input_tree.mouseMoveEvent = lambda e: self.tree_mouseMove(self.input_tree, e)
        self.input_tree.leaveEvent = lambda e: self.tree_leaveEvent(self.input_tree, e)

        self.port_type_output_btngroup = QtGui.QButtonGroup()
        self.port_type_output_btngroup.setExclusive(False)
        self.port_type_input_btngroup = QtGui.QButtonGroup()
        self.port_type_input_btngroup.setExclusive(False)

        for btn in self.conn_type_btngroup.buttons():
            btn.mousePressEvent = self.disable_check
            btn.keyPressEvent = self.disable_check

        self.port_type_output_group.setEnabled = lambda state: [b.setEnabled(state) for b in self.port_type_output_group.findChildren(QtGui.QCheckBox)]
        self.port_type_input_group.setEnabled = lambda state: [b.setEnabled(state) for b in self.port_type_input_group.findChildren(QtGui.QCheckBox)]
        self.port_cap_output_group.setEnabled = lambda state: [b.setEnabled(state) for b in self.port_cap_output_group.findChildren(QtGui.QCheckBox)]
        self.port_cap_input_group.setEnabled = lambda state: [b.setEnabled(state) for b in self.port_cap_input_group.findChildren(QtGui.QCheckBox)]
        self.client_type_output_btngroup.setId(self.client_type_output_user_chk, 1)
        self.client_type_output_btngroup.setId(self.client_type_output_kernel_chk, 2)
        self.client_type_input_btngroup.setId(self.client_type_input_user_chk, 1)
        self.client_type_input_btngroup.setId(self.client_type_input_kernel_chk, 2)
        for btn in self.client_type_output_btngroup.buttons()+self.client_type_input_btngroup.buttons():
            btn.mousePressEvent = self.disable_check
            btn.keyPressEvent = self.disable_check
        dest_widgets = [
                        (self.port_type_output_group.layout(), self.port_type_output_btngroup), 
                        (self.port_type_input_group.layout(), self.port_type_input_btngroup), 
                        ]
        self.port_type_output_label = CheckLabel('Port type', state=False)
        self.port_type_output_label.setAlignment(QtCore.Qt.AlignHCenter)
        self.port_type_output_group.layout().addWidget(self.port_type_output_label, 0, 0, 1, 3)
        self.port_type_input_label = CheckLabel('Port type', state=False)
        self.port_type_input_label.setAlignment(QtCore.Qt.AlignHCenter)
        self.port_type_input_group.layout().addWidget(self.port_type_input_label, 0, 0, 1, 3)

        for row, line in enumerate(port_type_checks):
            for col, txt in enumerate(line):
                if txt is None: continue
                btn_id = _get_key(port_type_to_str, txt)
                for layout, group in dest_widgets:
                    check = QtGui.QCheckBox(txt.replace('_', ' '))
                    check.mousePressEvent = self.disable_check
                    check.keyPressEvent = self.disable_check
                    check.setToolTip(port_type_tooltip[txt])
                    check.setVisible(False)
                    layout.addWidget(check, row+1, col)
                    group.addButton(check, btn_id)
            
        self.port_cap_output_btngroup = QtGui.QButtonGroup()
        self.port_cap_output_btngroup.setExclusive(False)
        self.port_cap_input_btngroup = QtGui.QButtonGroup()
        self.port_cap_input_btngroup.setExclusive(False)
        dest_widgets = [
                        (self.port_cap_output_group.layout(), self.port_cap_output_btngroup), 
                        (self.port_cap_input_group.layout(), self.port_cap_input_btngroup), 
                        ]
        self.port_cap_output_label = CheckLabel('Port capabilities', state=False)
        self.port_cap_output_label.setAlignment(QtCore.Qt.AlignHCenter)
        self.port_cap_output_group.layout().addWidget(self.port_cap_output_label, 0, 0, 1, 3)
        self.port_cap_input_label = CheckLabel('Port capabilities', state=False)
        self.port_cap_input_label.setAlignment(QtCore.Qt.AlignHCenter)
        self.port_cap_input_group.layout().addWidget(self.port_cap_input_label, 0, 0, 1, 3)

        for row, line in enumerate(port_cap_checks):
            for col, txt in enumerate(line):
                if txt is None: continue
                btn_id = _get_key(port_cap_to_str, txt)
                for layout, group in dest_widgets:
                    check = QtGui.QCheckBox(txt.replace('_', ' '))
                    check.mousePressEvent = self.disable_check
                    check.keyPressEvent = self.disable_check
                    check.setToolTip(port_cap_tooltip[txt])
                    check.setVisible(False)
                    layout.addWidget(check, row+1, col)
                    group.addButton(check, btn_id)

        self.alsa_thread = QtCore.QThread()
        self.alsa = AlsaMidi(self)
        self.alsa.moveToThread(self.alsa_thread)
        self.alsa.stopped.connect(self.alsa_thread.quit)
        self.alsa_thread.started.connect(self.alsa.run)
        self.alsa.client_start.connect(self.alsa_client_start)
        self.alsa.client_exit.connect(self.alsa_client_exit)
        self.alsa.port_start.connect(self.alsa_port_start)
        self.alsa.port_exit.connect(self.alsa_port_exit)
        self.alsa.conn_register.connect(self.alsa_conn_event)
        self.alsa_thread.start()
        self.seq = self.alsa.seq

        self.populate()

        self.connections = ConnectionWidget(self)
        self.connections.setMinimumWidth(40)
        self.views = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.views.setChildrenCollapsible(False)
        self.views.sizePolicy().setVerticalPolicy(QtGui.QSizePolicy.Expanding)
        self.views.setMinimumHeight(80)
        self.views.addWidget(self.output_tree)
        self.views.addWidget(self.connections)
        self.views.addWidget(self.input_tree)
        self.views_layout.addWidget(self.views)
        self.output_tree.paintEvent = self.output_tree_paint
        self.input_tree.paintEvent = self.input_tree_paint

        self.clients_combo = QtGui.QComboBox()
        self.clients_combo.addItems(['Show all clients', 'Hardware clients', 'Software clients'])
        self.clients_combo.currentIndexChanged.connect(self.port_show_set)
        self.system_chk = QtGui.QCheckBox('Show system clients')
        self.noexport_chk = QtGui.QCheckBox('Show hidden ports (NO_EXPORT)')
        self.toolBar.addWidget(self.clients_combo)
        self.toolBar.addSeparator()
        self.toolBar.addWidget(self.system_chk)
        self.toolBar.addWidget(self.noexport_chk)
        spacer = QtGui.QWidget()
        spacer.setMinimumWidth(20)
        spacer.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.toolBar.addWidget(spacer)
        popup = QtGui.QToolButton(self.toolBar)
        popup.setText('About... ')
        popup.setPopupMode(QtGui.QToolButton.InstantPopup)
        popup.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        popup.setMenu(self.menu())
        self.toolBar.addWidget(popup)
        

        self.hw_show = self.sw_show = True
        self.system_chk.toggled.connect(self.system_show_set)
        self.system_show_set(False, True)
        self.noexport_chk.toggled.connect(self.noexport_show_set)

        box_btns = [
                    (self.port_type_output_label, self.port_type_input_label, self.port_type_output_btngroup), 
                    (self.port_type_input_label, self.port_type_output_label, self.port_type_input_btngroup), 
                    (self.port_cap_output_label, self.port_cap_input_label, self.port_cap_output_btngroup), 
                    (self.port_cap_input_label, self.port_cap_output_label, self.port_cap_input_btngroup)
                    ]
        for sender, receiver, group in box_btns:
            sender.toggled.connect(lambda state, g=group: [btn.setVisible(state) for btn in g.buttons()])
            sender.toggled.connect(lambda state, r=receiver: r.setChecked(state))

        self.output_conn_table.itemDoubleClicked.connect(lambda i=i, pd=self.input_items: self.conn_select(i, pd))
        self.input_conn_table.itemDoubleClicked.connect(lambda i=i, pd=self.output_items: self.conn_select(i, pd))

#        self.eventFilter = self.splitterEvFilter
        self.splitter.setChildrenCollapsible(False)
        self.toolBar.installEventFilter(self)
        self.splitter.handle(1).installEventFilter(self)
        self.splitter.handle(2).installEventFilter(self)
        self.splitter_sizes = list(self.splitter.sizes())
        self.splitter.splitterMoved.connect(self.splitterMoved)

        self.spec_switch.hide()
        self.spec_groups = [w for w in self.spec_widget.findChildren(QtGui.QGroupBox)]
        self.spec_switch.clicked.connect(lambda state: [self.spec_switch.hide(), [w.show() for w in self.spec_groups if w.isEnabled()]])

        self.conn_switch.hide()
        self.conn_groups = [self.output_conn_group, self.input_conn_group]
        self.conn_switch.clicked.connect(lambda state: [self.conn_switch.hide(), [w.show() for w in self.conn_groups]])

    def menu(self):
        def about():
            title = 'About MidiGraph'
            msg = ('''
                   <b>MidiGraph</b><br/>
                   a Midi graph inspector for GNU/Linux<br/>
                   written by Maurizio Berti<br/><br/>
                   Project repository:
                   <a href="https://github.com/MaurizioB/MidiGraph">GitHub</a><br/>
                   <br/>
                   client icons from Crystal KDE theme<br/>
                   by Everaldo Coelho
                   </center>
                   ''')
            return QtGui.QMessageBox.about(self, title, msg)
        menu = QtGui.QMenu()
        about_action = QtGui.QAction('About MidiPortGraph...', self)
        about_action.triggered.connect(about)
        about_qt = QtGui.QAction('About Qt...', self)
        about_qt.triggered.connect(lambda state: QtGui.QMessageBox.aboutQt(self))
        menu.addActions([about_action, about_qt])
        return menu

    def splitterMoved(self, pos, index):
        return
        print self.splitter.getRange(1), pos
        print self.splitter.handle(1).layout()

    def spec_groups_visible(self, state=True):
        if state:
            for w in self.spec_groups:
                if w.isEnabled():
                    w.show()
            self.spec_switch.hide()
        else:
            self.spec_switch.show()
            for w in self.spec_groups:
                w.hide()

    def conn_groups_visible(self, state=True):
        if state:
            for w in self.conn_groups:
                if w.isEnabled():
                    w.show()
            self.conn_switch.hide()
        else:
            self.conn_switch.show()
            for w in self.conn_groups:
                w.hide()

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.ContextMenu:
            return True
        if event.type() == QtCore.QEvent.MouseButtonDblClick:
            if source == self.splitter.handle(1):
                if not self.spec_switch.isVisible:
                    pass
        if event.type() == QtCore.QEvent.MouseMove:
            if source == self.splitter.handle(1):
                if event.pos().y() < -self.splitter.handleWidth():
                    if self.conn_switch.isVisible() and not self.spec_switch.isVisible():
                        self.conn_groups_visible()
                    elif self.spec_switch.isVisible():
                        self.spec_groups_visible()
                if event.pos().y() > self.spec_layout.geometry().height():
                    if not self.spec_switch.isVisible():
                        self.spec_groups_visible(False)
                    elif event.pos().y() > self.spec_layout.geometry().height()+self.input_conn_group.geometry().height():
                        self.conn_groups_visible(False)
            else:
                if self.conn_switch.isVisible() and event.pos().y() < -self.splitter.handleWidth():
                    self.conn_groups_visible()
                if not self.conn_switch.isVisible() and event.pos().y() > self.input_conn_group.geometry().height():
                    self.conn_groups_visible(False)
#            print self.splitter.sizes()[0], self.splitter.widget(0).mapFrom(self, source.mapTo(self, event.pos()))
        return QtGui.QSplitter.eventFilter(self, source, event)

    @QtCore.pyqtSlot(int)
    def port_show_set(self, index, force=False):
        if index == 0:
            self.system_chk.setEnabled(True)
            self.hw_show = self.sw_show = True
        elif index == 1:
            self.system_chk.setEnabled(True)
            self.hw_show = True
            self.sw_show = False
        else:
            self.system_chk.setEnabled(False)
            self.hw_show = False
            self.sw_show = True
        self.system_show_set(True if self.system_chk.isChecked() and self.hw_show else False, True)
        for client in set(self.output_client_items.keys()+self.input_client_items.keys()):
            if client.id == 0: continue
            show = self.hw_show if client.type == 2 else self.sw_show
            output_item = self.output_client_items.get(client)
            if output_item:
                if not any([output_item.child(row).data(VisibleRole).toPyObject() for row in range(output_item.rowCount())]):
                    show = False
                output_item.setData(show, VisibleRole)
                if force:
                    output_item.emitDataChanged()
            input_item = self.input_client_items.get(client)
            if input_item:
                for row in range(input_item.rowCount()):
                    port_item = input_item.child(row)
                    if not port_item or not port_item.data(VisibleRole).toPyObject():
                        show = False
                        break
                input_item.setData(show, VisibleRole)
                if force:
                    input_item.emitDataChanged()

    def system_show_set(self, state, force=False):
        output_item = self.output_model.item(0)
        output_item.setData(state, VisibleRole)
        input_item = self.input_model.item(0)
        input_item.setData(state, VisibleRole)
        if force:
            output_item.emitDataChanged()
            input_item.emitDataChanged()

    def noexport_show_set(self, state):
        for port in set(self.input_items.keys()+self.output_items.keys()):
            for port_dict in [self.input_items, self.output_items]:
                item = port_dict.get(port)
                if item and alsaseq.SEQ_PORT_CAP_NO_EXPORT in port.caps:
                    item = self.output_items.get(port)
                    if item:
                        item.setData(state, VisibleRole)
                    item = port_dict.get(port)
                    if item:
                        item.setData(state, VisibleRole)
        self.port_show_set(self.clients_combo.currentIndex(), True)

    def tree_menu(self, pos):
        tree = self.sender()
        menu = QtGui.QMenu()
        expand = QtGui.QAction('Expand all', self)
        expand.triggered.connect(tree.expandAll)
        collapse = QtGui.QAction('Collapse all', self)
        collapse.triggered.connect(tree.collapseAll)
        menu.addActions([expand, collapse])
        menu.exec_(tree.mapToGlobal(pos))

    def output_tree_paint(self, event):
        self.connections.update()
        return QtGui.QTreeView.paintEvent(self.output_tree, event)

    def input_tree_paint(self, event):
        self.connections.update()
        return QtGui.QTreeView.paintEvent(self.input_tree, event)

    def populate(self):
#        Connection.highlight = False
        self.connection_group.hide()
        self.highlight_conn = []
        self.output_model = QtGui.QStandardItemModel()
        self.output_model.setHorizontalHeaderLabels(['Output/readable clients'])
        self.output_tree.setModel(self.output_model)
        self.input_model = QtGui.QStandardItemModel()
        self.input_model.setHorizontalHeaderLabels(['Input/writable clients'])
        self.input_tree.setModel(self.input_model)
        self.output_items = {}
        self.output_client_items = {}
        self.input_items = {}
        self.input_client_items = {}
        for client_id, port_dict in sorted(self.graph.port_id_dict.items()):
            client = self.graph.client_id_dict[client_id]
            inputs = []
            outputs = []
            for port_id, port in port_dict.items():
                port_item = QtGui.QStandardItem(port.name)
                port_item.setData(client, ClientRole)
                port_item.setData(port, PortRole)
                port_item.setData(port.id, IdRole)
                port_item.setData(True, VisibleRole)
                if port.is_duplex:
                    self.output_items[port] = port_item
                    outputs.append(port_item)
                    twin_item = QtGui.QStandardItem(port.name)
                    twin_item.setData(client, ClientRole)
                    twin_item.setData(port, PortRole)
                    twin_item.setData(port.id, IdRole)
                    twin_item.setData(True, VisibleRole)
                    inputs.append(twin_item)
                    self.input_items[port] = twin_item
                elif port.is_output:
                    self.output_items[port] = port_item
                    outputs.append(port_item)
                elif port.is_input:
                    self.input_items[port] = port_item
                    inputs.append(port_item)
                else:
                    del port_item
            if outputs:
                client_item = QtGui.QStandardItem('{}'.format(client.name))
                client_item.setData(client, ClientRole)
                client_item.setData(client.id, IdRole)
                client_item.setData(True, VisibleRole)
                client_item.setData(client_icon(client), QtCore.Qt.DecorationRole)
                self.output_client_items[client] = client_item
                self.output_model.appendRow(client_item)
                [client_item.appendRow(i) for i in outputs]
            if inputs:
                client_item = QtGui.QStandardItem('{}'.format(client.name))
                client_item.setData(client, ClientRole)
                client_item.setData(client.id, IdRole)
                client_item.setData(True, VisibleRole)
                client_item.setData(client_icon(client), QtCore.Qt.DecorationRole)
                self.input_client_items[client] = client_item
                self.input_model.appendRow(client_item)
                [client_item.appendRow(i) for i in inputs]
        self.output_model.dataChanged.connect(self.visible_changed)
        self.input_model.dataChanged.connect(self.visible_changed)
        for port in set(self.input_items.keys()+self.output_items.keys()):
            if port.client.id == 0:
                item = self.output_client_items.get(port.client)
                if item:
                    item.setData(False, VisibleRole)
                item = self.input_client_items.get(port.client)
                if item:
                    item.setData(False, VisibleRole)
            if alsaseq.SEQ_PORT_CAP_NO_EXPORT in port.caps:
                item = self.output_items.get(port)
                if item:
                    item.setData(False, VisibleRole)
                item = self.input_items.get(port)
                if item:
                    item.setData(False, VisibleRole)

        self.output_tree.currentChanged = lambda current, prev: self.item_select(self.output_tree, current)
        self.input_tree.currentChanged = lambda current, prev: self.item_select(self.input_tree, current)
        self.output_tree.expandAll()
        self.input_tree.expandAll()

    def tree_mouseMove(self, tree, event):
        model = tree.model()
        index = tree.indexAt(event.pos())
        item = model.itemFromIndex(index)
        if not item: return
        if tree == self.output_tree:
            target = 'dest'
            item_dict = self.input_items
        else:
            target = 'src'
            item_dict = self.output_items
        if index.parent() == tree.rootIndex():
            self.highlight_conn = []
            for row in range(item.rowCount()):
                conns = item.child(row).data(PortRole).toPyObject().connections
                self.highlight_conn.extend(conns.output if tree==self.output_tree else conns.input)
            self.highlight_items([getattr(conn, target) for conn in self.highlight_conn], item_dict)
            self.connections.update()
            return
        conns = item.data(PortRole).toPyObject().connections
#        conn_list = connections.output if tree==self.output_tree else connections.input
        self.highlight_conn = conns.output if tree==self.output_tree else conns.input
        self.highlight_items([getattr(conn, target) for conn in self.highlight_conn], item_dict)
        self.connections.update()

    def highlight_items(self, conn_list, item_dict):
        for port, item in item_dict.items():
            if not item.data(VisibleRole).toPyObject(): continue
            setBold(item, True if port in conn_list else False)

    def tree_leaveEvent(self, tree, event):
        self.highlight_conn = []
        self.highlight_items([], self.input_items if tree==self.output_tree else self.output_items)

    def visible_changed(self, index, br):
        model = index.model()
        tree = self.output_tree if self.output_tree.model() == model else self.input_tree
        item = model.itemFromIndex(index)
        if index.parent() == tree.rootIndex():
            tree.setRowHidden(item.row(), index.parent(), not item.data(VisibleRole).toPyObject())
            return
        for row in range(model.rowCount()):
            client_item = model.item(row)
            if not client_item.hasChildren(): continue
            if not client_item.data(VisibleRole).toPyObject(): continue
            if not any([client_item.child(row).data(VisibleRole).toPyObject() for row in range(client_item.rowCount())]):
                tree.setRowHidden(model.indexFromItem(client_item).row(), tree.rootIndex(), True)
            else:
                tree.setRowHidden(model.indexFromItem(client_item).row(), tree.rootIndex(), False)

    def item_select(self, sender, index):
        if sender == self.output_tree:
            tree = self.output_tree
            model = self.output_model
            cid_edit = self.output_client_id_edit
            cname_edit = self.output_client_name_edit
            pid_edit = self.output_port_id_edit
            pname_edit = self.output_port_name_edit
            type_group = self.port_type_output_btngroup
            cap_group = self.port_cap_output_btngroup
            client_group = self.client_type_output_btngroup
            type_box = self.port_type_output_group
            cap_box = self.port_cap_output_group
            conn_table = self.output_conn_table
            dir = 'output'
            other = 'dest'
        else:
            tree = self.input_tree
            model = self.input_model
            cid_edit = self.input_client_id_edit
            cname_edit = self.input_client_name_edit
            pid_edit = self.input_port_id_edit
            pname_edit = self.input_port_name_edit
            type_group = self.port_type_input_btngroup
            cap_group = self.port_cap_input_btngroup
            client_group = self.client_type_input_btngroup
            type_box = self.port_type_input_group
            cap_box = self.port_cap_input_group
            conn_table = self.input_conn_table
            dir = 'input'
            other = 'src'
        for btn in type_group.buttons()+cap_group.buttons():
            btn.setChecked(False)
        if index.parent() == tree.rootIndex():
            type_box.setEnabled(False)
            cap_box.setEnabled(False)
            client = model.itemFromIndex(index).data(ClientRole).toPyObject()
            cid_edit.setText(str(client.id))
            cname_edit.setText(client.name)
            pid_edit.setText('')
            pid_edit.setEnabled(False)
            pname_edit.setText('')
            pname_edit.setEnabled(False)
            conn_table.clear()
            conn_table.setColumnCount(0)
        else:
            type_box.setEnabled(True)
            cap_box.setEnabled(True)
            item = model.itemFromIndex(index)
            client = model.itemFromIndex(index.parent()).data(ClientRole).toPyObject()
            port = item.data(PortRole).toPyObject()
            cid_edit.setText(str(client.id))
            cname_edit.setText(client.name)
            pid_edit.setText(str(port.id))
            pid_edit.setEnabled(True)
            pname_edit.setText(port.name)
            pname_edit.setEnabled(True)
            for cap in port.caps:
                cap_group.button(cap).setChecked(True)
            for t in port.type:
                type_group.button(t).setChecked(True)

            conn_list = getattr(port.connections, dir)
            conn_list = sorted(conn_list, key=lambda c: (getattr(c, other).client.id, getattr(c, other).id))
            conn_table.setColumnCount(5)
            conn_table.setRowCount(len(conn_list))
            conn_table.setHorizontalHeaderLabels(['Port', 'Excl', 'Que', 'Real', 'Upd'])
            for c in range(1, 5):
                conn_table.horizontalHeader().setResizeMode(c, QtGui.QHeaderView.Fixed)
            conn_table.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
            conn_table.verticalHeader().setResizeMode(QtGui.QHeaderView.Fixed)
            for row, conn in enumerate(conn_list):
                port = getattr(conn, other)
                item = QtGui.QTableWidgetItem(port.name)
                item.setData(PortRole, port)
                conn_table.setItem(row, 0, item)
                for c, key in enumerate(['exclusive', 'queue', 'time_real', 'time_update']):
                    widget = QtGui.QWidget()
                    check = QtGui.QCheckBox()
                    check.setChecked(True if conn.info[key] else False)
                    check.mousePressEvent = self.disable_check
                    check.keyPressEvent = self.disable_check
                    layout = QtGui.QHBoxLayout()
                    layout.setAlignment(QtCore.Qt.AlignHCenter)
                    widget.setLayout(layout)
                    layout.addWidget(check)
                    conn_table.setCellWidget(row, 1+c, widget)
            conn_table.resizeColumnsToContents()
            conn_table.resizeRowsToContents()
            w = max([conn_table.columnWidth(c) for c in range(1, 5)])
            for c in range(1, 5):
                conn_table.setColumnWidth(c, w)
        client_group.button(client.type).setChecked(True)

        def hide_conn():
            self.connection_group.setEnabled(False)
            self.connection_group.hide()
        if self.output_tree.currentIndex().row() < 0:
            hide_conn()
            return
        output_port = self.output_model.itemFromIndex(self.output_tree.currentIndex()).data(PortRole).toPyObject()
        if output_port is None or self.input_tree.currentIndex().row() < 0:
            hide_conn()
            return
        input_port = self.input_model.itemFromIndex(self.input_tree.currentIndex()).data(PortRole).toPyObject()
        if input_port is None:
            hide_conn()
            return
        no_conn = True
        for conn in self.graph.connections[output_port].output:
            if input_port == conn.dest:
                no_conn = False
                break
        if no_conn:
            hide_conn()
            return
        self.connection_group.setEnabled(True)
        if not self.spec_switch.isVisible():
            self.connection_group.show()
        for k, v in conn.info.items():
            getattr(self, 'conn_{}_chk'.format(k)).setChecked(True if v else False)

    def conn_select(self, table_item, port_dict):
        table_item = table_item.tableWidget().item(table_item.row(), 0)
        item = port_dict[table_item.data(PortRole).toPyObject()]
        model = item.model()
        if model == self.output_model:
            tree = self.output_tree
        else:
            tree = self.input_tree
        index = model.indexFromItem(item)
        tree.setCurrentIndex(index)
        tree.scrollTo(index)
        tree.selectionModel().setCurrentIndex(index, QtGui.QItemSelectionModel.Select)

    def alsa_client_start(self, *args):
        pass

    def alsa_client_exit(self, *args):
        pass

    def alsa_port_start(self, port):
        def create_client(client, client_dict, client_model):
            client_item = client_dict.get(client)
            if client_item: return client_item
            client_item = QtGui.QStandardItem('{}'.format(client.name))
            client_item.setData(client, ClientRole)
            client_item.setData(client.id, IdRole)
            client_item.setData(True, VisibleRole)
            client_item.setData(client_icon(client), QtCore.Qt.DecorationRole)
            client_dict[client] = client_item
            client_model.appendRow(client_item)
            return client_item

        if alsaseq.SEQ_PORT_CAP_NO_EXPORT in port.caps and self.noexport_chk.isChecked():
            visible = False
        else:
            visible = True
        client = port.client
        port_item = QtGui.QStandardItem(port.name)
        port_item.setData(client, ClientRole)
        port_item.setData(port, PortRole)
        port_item.setData(port.id, IdRole)
        port_item.setData(visible, VisibleRole)
        if port.is_duplex:
            self.output_items[port] = port_item
            client_item = self.output_client_items.get(client)
            if not client_item:
                client_item = create_client(client, self.output_client_items, self.output_model)
            client_item.appendRow(port_item)
            self.output_tree.expand(client_item.index())

            twin_item = QtGui.QStandardItem(port.name)
            twin_item.setData(client, ClientRole)
            twin_item.setData(port, PortRole)
            twin_item.setData(port.id, IdRole)
            twin_item.setData(visible, VisibleRole)
            self.input_items[port] = twin_item
            client_item = self.input_client_items.get(client)
            if not client_item:
                client_item = create_client(client, self.input_client_items, self.input_model)
            client_item.appendRow(port_item)
            self.input_tree.expand(client_item.index())
        elif port.is_output:
            self.output_items[port] = port_item
            client_item = self.output_client_items.get(client)
            if not client_item:
                client_item = create_client(client, self.output_client_items, self.output_model)
            client_item.appendRow(port_item)
            self.output_tree.expand(client_item.index())
        elif port.is_input:
            self.input_items[port] = port_item
            client_item = self.input_client_items.get(client)
            if not client_item:
                client_item = create_client(client, self.input_client_items, self.input_model)
            client_item.appendRow(port_item)
            self.input_tree.expand(client_item.index())
        self.port_show_set(self.clients_combo.currentIndex(), force=True)


    def alsa_port_exit(self, port):
        item = self.output_items.get(port)
        if item:
            client_item = item.parent()
            row = client_item.takeRow(item.index().row())
            if not client_item.hasChildren():
                self.output_model.takeRow(client_item.row())
            del row
        item = self.input_items.get(port)
        if item:
            client_item = item.parent()
            row = client_item.takeRow(item.index().row())
            if not client_item.hasChildren():
                self.input_model.takeRow(client_item.row())
            del row

    def alsa_conn_event(self, conn, state):
        if state:
            self.connections.append(conn)


    def disable_check(self, *args):
        pass

def main():
    app = QtGui.QApplication(sys.argv)
    win = PortGraph()
    win.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()


