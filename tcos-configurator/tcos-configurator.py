#!/usr/bin/env python
# -*- coding: UTF-8 -*-
##########################################################################
# TcosConfigurator writen by MarioDebian <mariodebian@gmail.com>
#
#    TcosConfigurator version __VERSION__
#
# Copyright (c) 2008 Mario Izquierdo <mariodebian@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
###########################################################################

import sys
import os
import glob

# for get_ip_address
import socket
import fcntl
import struct
#####################

import pygtk
pygtk.require('2.0')
from gtk import *
import gtk.glade

import time
import getopt
from gettext import gettext as _
from gettext import bindtextdomain, textdomain
from locale import setlocale, LC_ALL

from subprocess import Popen, PIPE, STDOUT
import popen2
from threading import Thread

import pwd

import gobject

#import threading
gtk.gdk.threads_init()
gobject.threads_init()



########################################################
#
#  Extends python-configobj this class use '=' instead of  ' = '
#
########################################################
from configobj import ConfigObj
class MyConfigObj (ConfigObj):

    def _write_line(self, indent_string, entry, this_entry, comment):
        """Write an individual line, for the write method"""
        # NOTE: the calls to self._quote here handles non-StringType values.
        if not self.unrepr:
            val = self._decode_element(self._quote(this_entry))
        else:
            val = repr(this_entry)
        return '%s%s%s%s%s' % (
            indent_string,
            self._decode_element(self._quote(entry, multiline=False)),
            self._a_to_u('='),
            val,
            self._decode_element(comment))
#############################################################


debug=False
PACKAGE="tcos-configurator"

# if exec from svn or sources dir
if os.path.isdir('./debian'):
    LOCALE_DIR = "./po/"
    GLADE_DIR = "./"
    IMG_DIR = "./images/"
    print "exec in sources dir"
else:
    GLADE_DIR = "/usr/share/tcos-configurator/"
    IMG_DIR = "/usr/share/tcos-configurator/images/"
    LOCALE_DIR = "/usr/share/locale/"

def print_debug(txt):
    if debug:
        print >> sys.stderr, "%s::%s" %("tcos-configurator", txt)
    return

def usage():
    print "tcos-configurator help:"
    print ""
    print "   tcos-configurator -d [--debug]  (write debug data to stdout)"
    print "   tcos-configurator -h [--help]   (this help)"


try:
    opts, args = getopt.getopt(sys.argv[1:], ":hd", ["help", "debug"])
except getopt.error, msg:
    print msg
    print "for command line options use tcosconfig --help"
    sys.exit(2)

# process options
for o, a in opts:
    if o in ("-d", "--debug"):
        print "DEBUG ACTIVE"
        debug = True
    if o in ("-h", "--help"):
        usage()
        sys.exit()

################################################################################
DHCP_CONF=[
['# dhcpd.conf',"# generated by __PROGRAM__ on date __DATE__"] ,

['ddns-update-style ad-hoc;',
    'option subnet-mask __MASK__;',
    '#option domain-name "tcos-domain.org";',
    'option option-128 code 128 = string;',
    'option option-129 code 129 = text;',
    'get-lease-hostnames true;',
],

['shared-network AULAMAX {',
    "\t\tsubnet __NET__ netmask __MASK__ {",
    "\t\toption domain-name-servers __DNS__;",
    "\t\toption broadcast-address __BROADCAST__;",
    "\t\toption routers __ROUTERS__;",
    "\t\tnext-server __SERVERIP__;",
    "\t\trange dynamic-bootp __STARTIP__ __ENDIP__;",
    "\t\tfilename \"__BOOTMODE__\";",
  "\t}",
"}"
],
]

GDM_CONFIG={
"xdmcp":[
    {"Enable":"true"}
    ],
"security":[
    {"AllowRemoteAutoLogin":"true"},
    {"DisallowTCP":"false"}
    ],
"daemon":[
    {"TimedLoginEnable":"__AUTOLOGIN__"},
    {"TimedLogin":"/usr/sbin/tcos-gdm-autologin|"},
    {"TimedLoginDelay":"__TIMEOUT__"}
    ],
}

GDM_CONF_FILE="/etc/gdm/gdm.conf"
################################################################################

class TcosStandalone:
    def __init__(self):
        print_debug("__init__()")
        
        # vars
        self.v={}
        
        gtk.glade.bindtextdomain(PACKAGE, LOCALE_DIR)
        gtk.glade.textdomain(PACKAGE)

        # gettext support
        setlocale( LC_ALL )
        bindtextdomain( PACKAGE, LOCALE_DIR )
        textdomain( PACKAGE )
        
        self.BOOT_MODES=[
                [_("TCOS and Backharddi"), "/pxelinux.0" ],
                [_("Only TCOS"),           "/tcos/pxelinux.0" ],
                [_("Only Backharddi"),     "/backharddi/pxelinux.0"],
                ]
        
        
        # Widgets
        self.ui = gtk.glade.XML(GLADE_DIR + 'tcos-configurator.glade')
        self.mainwindow = self.ui.get_widget('mainwindow')
        self.mainwindow.set_icon_from_file(IMG_DIR +'tcos-icon-32x32.png')
        
        # close windows signals
        self.mainwindow.connect('destroy', self.quitapp )
        self.mainwindow.connect('delete_event', self.quitapp)
        
        self.button_quit=self.ui.get_widget("btn_quit")
        self.button_quit.connect('clicked', self.quitapp)
        
        self.window_autologin_help=self.ui.get_widget('window_autologin_help')
        self.window_autologin_help.set_icon_from_file(IMG_DIR +'tcos-icon-32x32.png')
        self.window_autologin_help.connect('destroy', self.hidehelp )
        self.window_autologin_help.connect('delete_event', self.hidehelp)
        
        # widgets
        self.w={}
        for widget in ['img_logo', 'combo_interfaces', 'txt_serverip', 'txt_startip', 
                       'txt_endip', 'btn_configure_dhcp', 'combo_boot_mode', 'hbox_dynamic',
                       'ck_static', 'btn_hostname_help', 'txt_hostname_prefix']:
            self.w[widget]=self.ui.get_widget(widget)
        
        self.w['img_logo'].set_from_file(IMG_DIR + 'tcos-logo.png')
        self.w['combo_interfaces'].connect('changed', self.combo_interface_change )
        self.w['btn_configure_dhcp'].connect('clicked', self.on_btn_configure_dhcp)
        self.w['txt_serverip'].connect('focus-out-event', self.on_serverip_blur )
        self.w['btn_hostname_help'].connect('clicked', self.on_btn_autologin_help)
        
        
        self.populate_select(self.w['combo_boot_mode'], self.BOOT_MODES)
        self.set_active_in_select(self.w['combo_boot_mode'], self.BOOT_MODES[0][0])
        
        self.interfaces=self.getNetInterfaces()
        self.configured_interfaces=self.read_etc_network_interfaces()
        if len(self.configured_interfaces) < 1:
            self.w['hbox_dynamic'].show()
        
        self.populate_select(self.w['combo_interfaces'],  self.interfaces )
        if len(self.interfaces) == 1:
            self.set_active_in_select(self.w['combo_interfaces'], self.interfaces[0][0])
        
        for widget in ['txt_serverip', 'txt_startip', 'txt_endip', 'combo_boot_mode']:
            self.w[widget].connect('changed', self.set_dhcp_modified)
        
        self.w['lbl_dhcp']=self.ui.get_widget('lbl_dhcp')
        self.w['lbl_dhcp'].set_text("")
        self.dhcp_modified=False
        
        
        print_debug("configured_interfaces %s"%self.configured_interfaces)
        print_debug("detected_interfaces %s"%self.interfaces)
        
        # users
        for widget in ['scale_number_users', 'txt_prefix', 'txt_groups', 'lbl_users', 'btn_commit_users']:
            self.w[widget]=self.ui.get_widget(widget)
        
        self.w['scale_number_users'].connect('value_changed', self.on_scale_number_users)
        self.on_scale_number_users(self.w['scale_number_users'])
        
        self.w['btn_commit_users'].connect('clicked', self.on_btn_commit_users)
        
        
        # remote login
        for widget in ['ck_remotelogin', 'ck_autologin', 'scale_autologin', 'btn_commit_login', 'btn_autologin_help', 'lbl_login']:
            self.w[widget]=self.ui.get_widget(widget)
        
        self.w['ck_remotelogin'].connect('toggled', self.on_ck_remotelogin)
        self.w['ck_autologin'].connect('toggled', self.on_ck_remotelogin)
        self.w['scale_autologin'].connect('value_changed', self.on_ck_remotelogin)
        self.w['btn_commit_login'].connect('clicked', self.on_btn_commit_login)
        
        self.w['btn_autologin_help'].connect('clicked', self.on_btn_autologin_help)
        

    def on_serverip_blur(self, widget, event):
        value=widget.get_text()
        if value == "": return
        self.w['txt_startip'].set_text(".".join(value.split('.')[0:3]) + ".101")
        self.w['txt_endip'].set_text(  ".".join(value.split('.')[0:3]) + ".131")
        self.w['lbl_dhcp'].set_text("")

    def combo_interface_change(self, widget):
        seliface=self.read_select_value(widget)
        for iface in self.interfaces:
            if iface[0] == seliface and iface[1] != None:
                self.w['txt_startip'].set_text(".".join(iface[1].split('.')[0:3]) + ".101")
                self.w['txt_endip'].set_text(  ".".join(iface[1].split('.')[0:3]) + ".131")
                self.w['txt_serverip'].set_text(iface[1])
                self.set_dhcp_modified()
                self.w['lbl_dhcp'].hide()
                self.w['hbox_dynamic'].hide()
                self.w['ck_static'].set_active(False)
            if iface[1] == None:
                self.w['hbox_dynamic'].show()
                self.w['ck_static'].set_active(True)
                self.w['lbl_dhcp'].set_markup( _("WARNING:\n<b>Network interface don't have IP</b>") )
                self.w['lbl_dhcp'].show()

    def set_dhcp_modified(self, *args):
        self.dhcp_modified=True
        self.w['btn_configure_dhcp'].set_sensitive(True)

    def on_btn_configure_dhcp(self, *args):
        th=Thread(target=self.configureDHCP)
        th.start()

    def hidehelp(self, *args):
        self.window_autologin_help.hide()
        return True

    def on_btn_autologin_help(self, widget):
        self.window_autologin_help.show()
##############    login #######################################################

    def on_ck_remotelogin(self, widget):
        if self.w['ck_remotelogin'].get_active():
            self.w['ck_autologin'].set_sensitive(True)
            self.w['scale_autologin'].set_sensitive(True)
        else:
            self.w['ck_autologin'].set_sensitive(False)
            self.w['scale_autologin'].set_sensitive(False)
        self.w['btn_commit_login'].set_sensitive(True)

    def on_btn_commit_login(self, widget):
        if self.w['ck_remotelogin'].get_active():
            self.enable_remotelogin()
        else:
            self.disable_remotelogin()
        self.w['btn_commit_login'].set_sensitive(False)

    def enable_remotelogin(self):
        self.SetVar("xdmcp", "Enable", "true")
        self.SetVar("xdmcp", "MaxSessions", "30")
        if os.path.exists("/usr/lib/gdm/gdmgreeter"):
            self.SetVar("daemon", "RemoteGreeter", "/usr/lib/gdm/gdmgreeter")
        self.SetVar("daemon", "TimedLogin", "/usr/sbin/tcos-gdm-autologin|")
        if self.w['ck_autologin'].get_active():
            self.SetVar("daemon", "TimedLoginEnable", "true")
        else:
            self.SetVar("daemon", "TimedLoginEnable", "false")
        self.SetVar("daemon", "TimedLoginDelay", str( int(self.w['scale_autologin'].get_value()) ) )
        # show message to reboot required
        self.w['lbl_login'].set_markup( _("<b>Reboot required (or restart gdm daemon) to enable new GDM settings</b>") )
        self.w['lbl_login'].show()
        return

    def disable_remotelogin(self):
        self.SetVar("xdmcp","Enable","false")

    def SetVar(self, section, key, value, do=True):
        GDMCONF=GDM_CONF_FILE
        # try to edit correct file (Ubuntu use -custom file)
        if os.path.isfile(GDM_CONF_FILE + "-custom"):
            GDMCONF=GDM_CONF_FILE+"-custom"

        if os.path.isfile("/etc/gdm/gdm-cdd.conf"):
            GDMCONF="/etc/gdm/gdm-cdd.conf"

        if not do:
            print_debug("NOACTION: SetVar() gdm.conf=%s section=%s key=%s value=%s" 
                        %(GDMCONF, section,key,value) )
            return
            
        config=MyConfigObj( os.path.realpath(GDMCONF) )
        print_debug("setting gdm=%s section=[%s] key=%s value=%s" %(GDMCONF, section, key, value) )
        config[section][key] = value
        try:
            config.write()
            return True
        except:
            print_debug("Error, can't write in %s" %(GDMCONF))
            return False

############## users ##########################################################
    def on_scale_number_users(self, widget):
        num=int(widget.get_value())
        prefix=self.w['txt_prefix'].get_text()
        init=1
        end=num
        self.w['lbl_users'].set_text(_("Creating from %(prefix)s%(init)02d to %(prefix)s%(end)02d") %{"prefix":prefix, "init":init, "end":end} )
        self.w['lbl_users'].show()
        self.w['btn_commit_users'].set_sensitive(True)

    def on_btn_commit_users(self, widget):
        th=Thread(target=self.createUsers)
        th.start()


    def userExists(self, username):
        try:
            pwd.getpwnam(username)
            return True
        except:
            return False

    def createUsers(self):
        number=int(self.w['scale_number_users'].get_value())
        user_prefix=self.w['txt_prefix'].get_text()
        groups=self.w['txt_groups'].get_text()
        
        gtk.gdk.threads_enter()
        self.w['btn_commit_users'].set_sensitive(False)
        self.w['lbl_users'].set_text("")
        gtk.gdk.threads_leave()
        
        for i in range(number):
            # range starts in 0
            i="%02d"%(i+1)
            username="%s%s"%(user_prefix, i)
            if not self.userExists(username):
                print_debug("Creating username %s"%username)
                gtk.gdk.threads_enter()
                self.w['lbl_users'].set_text( _("Creating user: '%s'") %username )
                gtk.gdk.threads_leave()
                self.exe_cmd("useradd -m %s -p%s -s /bin/bash -d /home/%s" %(username, username, username))
                self.exe_cmd("echo %s:%s | chpasswd" %(username, username))
                self.exe_cmd("adduser %s fuse" %(username) )
            else:
                print_debug("User already exists: %s"%username)
                gtk.gdk.threads_enter()
                self.w['lbl_users'].set_text( _("User already exists: '%s'") %username )
                gtk.gdk.threads_leave()
                time.sleep(1)
        
        gtk.gdk.threads_enter()
        self.w['lbl_users'].set_markup( _("<b>Done</b>") )
        gtk.gdk.threads_leave()

######################network ##########################################


    def get_ip_address(self, ifname):
        print_debug("get_ip_address() ifname=%s" %(ifname) )
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15])
        )[20:24])


    def getNetInterfaces(self):
        interfaces=[]
        for edir in glob.glob("/sys/class/net/*"):
            edir=os.path.basename(edir)
            if edir != "lo" and edir != "sit0" and not edir.startswith("vbox") and not edir.startswith("vmnet"):
                IP=None
                try:
                    IP=self.get_ip_address(edir)
                    #interfaces.append( [edir, IP] )
                except:
                    pass
                interfaces.append( [edir, IP])
        return interfaces

    def read_etc_network_interfaces(self):
        interfaces={}
        curiface=None
        try:
            f=open("/etc/network/interfaces",'r')
        except:
            print_debug("Error, can't read /etc/network/interfaces")
            return interfaces
        data=f.readlines()
        f.close()
        for line in data:
            line=line.strip()
            if len(line) == 0: continue
            if line.startswith('#'): continue
            if line.startswith("iface"):
                curiface=line.split()[1]
                interfaces[curiface]={}
            if curiface and line.startswith('address'):
                interfaces[curiface]['address']=line.split()[1]
            if curiface and line.startswith('netmask'):
                interfaces[curiface]['netmask']=line.split()[1]
            if curiface and line.startswith('gateway'):
                interfaces[curiface]['gateway']=line.split()[1]
            if curiface and line.startswith('network'):
                interfaces[curiface]['network']=line.split()[1]
            if curiface and line.startswith('broadcast'):
                interfaces[curiface]['broadcast']=line.split()[1]
            if curiface and line.startswith('dns-nameservers'):
                interfaces[curiface]['dns-nameservers']=line.split()[1:]
        return interfaces
                

    def configure_static(self, data):
        newdata=[]
        curiface=None
        added=False
        print data
        try:
            f=open("/etc/network/interfaces",'r')
        except:
            print_debug("Error, can't read /etc/network/interfaces")
            return False
        ifile=f.readlines()
        f.close()
        for line in ifile:
            sline=line.strip()
            if sline.startswith('iface'):
                curiface=sline.split()[1]
            if not added and curiface and curiface == data['iface']:
                newdata.append("# added by tcos-configurator")
                newdata.append("auto %s" %curiface)
                newdata.append("iface %s inet static" %curiface)
                for opt in data:
                    if opt == 'iface': continue
                    if opt == 'gateway': continue
                    newdata.append("\t%s %s" %(opt, data[opt]) )
                newdata.append("\n\n")
                added=True
            if added and curiface == data['iface']:
                continue
            if (sline.startswith('auto') or sline.startswith('allow') ) and sline.split()[1] == data['iface']:
                continue 
                    
            newdata.append(line.replace('\n','') )
        
        try:
            f=open("/etc/network/interfaces", 'w')
        except:
            return False
        for line in newdata:
            f.write(line)
        f.close()
        
        return True

################### combo stuff ##############################

    def populate_select(self, widget, values):
        valuelist = gtk.ListStore(str)
        for value in values:
            valuelist.append([value[0]])
        widget.set_model(valuelist)
        #widget.set_text_column(0)
        if widget.get_text_column() != 0:
            widget.set_text_column(0)
        model=widget.get_model()
        return

    def set_active_in_select(self, widget, default):
        model=widget.get_model()
        for i in range(len(model)):
            if model[i][0] == default:
                print_debug ("set_active_in_select() default is '%s', index %d" %( model[i][0] , i ) )
                widget.set_active(i)
        return

    def read_select_value(self, widget):
        selected=-1
        try:
            selected=widget.get_active()
        except:
            print_debug ( "read_select() ERROR reading " )
        model=widget.get_model()
        value=model[selected][0]
        print_debug ( "read_select() reading %s" %(value) )
        return value

################################################################################
    def parse_dhcp(self, line, options):
        for option in options:
            #print_debug("line %s replace %s with %s"%(line, option, options[option]))
            line=line.replace(option, options[option])
        print_debug(line)
        return line

    def write_into_etc_host(self, newline):
        ip=newline[0]
        hostname=newline[1]
        # check if exists
        f=open("/etc/hosts", "r")
        data=f.readlines()
        f.close()
        for line in data:
            line=line.replace('\n','')
            if ip + " " in line or ip + '\t' in line:
                print_debug ( "IP %s is in /etc/hosts" %(ip) )
                return True
        try:
            print_debug ("Adding %s %s" %(ip, hostname) )
            if noaction:
                print_debug("NOACTION: AddHost() hostname=%s, ip=%s" %(hostname,ip) )
            else:
                f=open("/etc/hosts", "a")
                f.write("%s\t%s\n" %(ip, hostname) )
                f.close()
                return True
        except:
            print "Error editting /etc/hosts, are you root?"
            return False

    def configureDHCP(self, *args):
        # get data
        gtk.gdk.threads_enter()
        self.w['btn_configure_dhcp'].set_sensitive(False)
        self.w['lbl_dhcp'].set_text( _("Configuring DHCP service...") )
        self.w['lbl_dhcp'].show()
        gtk.gdk.threads_leave()
        
        boot_mode=self.read_select_value(self.w['combo_boot_mode'])
        boot_filename="/pxelinux.0"
        for boot in self.BOOT_MODES:
            if boot[0] == boot_mode:
                boot_filename=boot[1]
        # get server_ip
        server_iface=self.read_select_value(self.w['combo_interfaces'])
        if self.configured_interfaces.has_key(server_iface) and len(self.configured_interfaces[server_iface]) > 1:
            server_ip=self.configured_interfaces[server_iface]['address']
            gateway=self.configured_interfaces[server_iface]['gateway']
            netmask=self.configured_interfaces[server_iface]['netmask']
            network=self.configured_interfaces[server_iface]['network']
            broadcast=self.configured_interfaces[server_iface]['broadcast']
        else:
            server_ip=None
            for interface in self.interfaces:
                if interface[0] == server_iface:
                    server_ip=interface[1]
            if server_ip == None:
                server_ip=self.w['txt_serverip'].get_text()
            # gateway
            gateway=self.exe_cmd("ip route| grep %s| awk '/^default/ {print $3}'"%server_iface)
            if gateway == [] or gateway == "":
                print_debug("gateway not found, using server_ip")
                gateway=server_ip
            broadcast=".".join( server_ip.split('.')[0:-1]) + ".255"
            netmask="255.255.255.0"
            network=".".join( server_ip.split('.')[0:-1]) + ".0"
        
        # read dns
        f=open("/etc/resolv.conf", 'r')
        dns=[]
        for line in f.readlines():
            if line.startswith("nameserver"):
                dns.append(line.split(' ')[1].strip())
        f.close()
        
        options={
        "__PROGRAM__":PACKAGE,
        "__DATE__":time.ctime(),
        "__MASK__":netmask,
        "__NET__":network,
        "__DNS__":" ".join(dns),
        "__BROADCAST__":broadcast,
        "__ROUTERS__":gateway,
        "__SERVERIP__":server_ip,
        "__STARTIP__":self.w['txt_startip'].get_text(),
        "__ENDIP__":self.w['txt_endip'].get_text(),
        "__BOOTMODE__":boot_filename
        }
        # backup old conf file
        
        # generate /etc/dhcp3/dhcpd.conf
        new_file=[]
        for block in DHCP_CONF:
            for line in block:
                new_file.append(self.parse_dhcp(line, options))
        
        
        try:
            f=open("/etc/dhcp3/dhcpd.conf", 'w')
            for line in new_file:
                f.write(line)
            f.close()
        except:
            # error writing
            gtk.gdk.threads_enter()
            self.w['lbl_dhcp'].set_markup( _("<b>Error writing /etc/dhcp3/dhcpd.conf.</b>\nAre you root?") )
            gtk.gdk.threads_leave()
            time.sleep(4)
        
        # edit /etc/hosts
        ip_pref=".".join(self.w['txt_startip'].get_text().split('.')[0:3])
        ip_start=int(self.w['txt_startip'].get_text().split('.')[-1])
        ip_end=int(self.w['txt_endip'].get_text().split('.')[-1])
        txt_prefix=self.w['txt_hostname_prefix'].get_text()
        
        for ip in range ( (ip_end - ip_start) ):
            ip=ip_start + ip
            if ip > 100:
                ipname=ip-100
            self.write_into_etc_host( ["%s.%d"%(ip_pref, ip), "%s%02d"%(txt_prefix, ipname) ]  )
        
        
        # read ck_static
        data={
            "iface":server_iface,
            "address":server_ip,
            "gateway":gateway,
            "netmask":netmask,
            "network":network,
            "broadcast":broadcast,
            }
        if self.w['ck_static'].get_active():
            if self.configure_static(data):
                gtk.gdk.threads_enter()
                self.w['lbl_dhcp'].set_text( _("Configured static network") )
                gtk.gdk.threads_leave()
                time.sleep(1)
            else:
                gtk.gdk.threads_enter()
                self.w['lbl_dhcp'].set_markup( _("ERROR:<b>Error configuring static network.</b>") )
                gtk.gdk.threads_leave()
                time.sleep(4)
        
        
        gtk.gdk.threads_enter()
        self.w['lbl_dhcp'].set_text( _("Restarting DHCP service...") )
        gtk.gdk.threads_leave()
        
        result=self.exe_cmd("/etc/init.d/dhcp3-server restart")
        fail=False
        for line in result:
            if "fail" in line:
                fail=True
        
        gtk.gdk.threads_enter()
        if not fail:
            self.w['lbl_dhcp'].set_markup( _("<b>Done</b>") )
        else:
            self.w['lbl_dhcp'].set_markup( _("<b>Error restarting DHCP server.</b>") )
        gtk.gdk.threads_leave()
        

################################################################################

        
    def exe_cmd(self, cmd, verbose=1):
        print_debug("exe_cmd() cmd=%s" %cmd)
        output=[]
        (stdout, stdin) = popen2.popen2(cmd)
        stdin.close()
        for line in stdout:
            if line != '\n':
                line=line.replace('\n', '')
                output.append(line)
        if len(output) == 1:
            return output[0]
        elif len(output) > 1:
            if verbose==1:
                print_debug ( "exe_cmd(%s) %s" %(cmd, output) )
            return output
        else:
            if verbose == 1:
                print_debug ( "exe_cmd(%s)=None" %(cmd) )
            return []


    def quitapp(self,*args):
        print_debug ( "Exiting" )
        self.mainloop.quit()

    def run (self):
        self.mainloop = gobject.MainLoop()
        try:
            self.mainloop.run()
        except KeyboardInterrupt: # Press Ctrl+C
            self.quitapp()
   


if __name__ == '__main__':
    app = TcosStandalone ()
    # Run app
    app.run ()