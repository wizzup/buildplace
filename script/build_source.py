#!/usr/bin/python
# Copyright (c) 2012 All Right Reserved, Wisut Hantanong
#
# This file is part of buildplace.
#
# buildplace is free software: you can redistribute it and/or modify
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option) any later version.
#
# buildplace is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with buildplace.  If not, see <http://www.gnu.org/licenses/>.

import sys, os, yaml, logging, Tkinter as tkinter, time, subprocess

#FIXME:HARDCODE: get terminal dimension from system instead of hard-coding
# btw terminal is use for debug purpose only
TERM_WIDTH = 150

# global variables for inter-function communication
logger = logging.getLogger('buildplace') # logger for debuging
ENV = {} # global environ, we use this modified ENV in addition of per-source envs and system os.environ
CONFIGS = {} # program configuration
# TODO:try to minimize value passing via UI by using CONFIGS when applicable, this will help in UI redesign process
UIS = {} # for cross-function UI update
APP = 0 # tk app reference
TITLE='buildplace 0.0.1'

# script entry point
def main():
	# DEBUG: clear console for easy debug message reading
	if sys.platform == 'linux2': os.system('clear')

	global CONFIGS # need this to tell python that we will write to global CONFIGS
	global UIS # need this too for modifying the global UIS

	CONFIGS = loadconfig() # we only want the log_dir
	if CONFIGS == {}:
		quit() # nothing to do if there is no valid configuration

	logger.debug('CONFIGS {}'.format(CONFIGS))

	print 'Looking for log_dir in config file'
	log_dir = CONFIGS['common']['log_dir']

	initlogger(log_dir)

	logger.debug('main: logger init')
	logger.debug('CONFIGS: {0}'.format(CONFIGS))

	create_main_window()

	# application main loop
	APP.mainloop()

	#inject_default_config(configs)

	#save_config(configs)

	logger.debug('main: exit')
	return

# this enable config editing without script restart
def reload_config():
	global CONFIGS
	global UIS

	CONFIGS = loadconfig()

	# clear and fill listbox with entry in config file
	UIS['sourcelistbox'].delete(0, tkinter.END)
	UIS['status'].set('Nothing selected')
	for w in UIS['source_detail'].winfo_children():
		w.destroy()

	print 'source'
	sources = {}
	for src in CONFIGS['source'] if 'source' in CONFIGS else {}:
		sources[src] = CONFIGS['source'][src] # get source sub-item
		print '  name {0} version {1}'.format(src, sources[src]['version'])

	for src in sources:
		UIS['sourcelistbox'].insert(tkinter.END, src)

	return

# create main tk window with source selection listbox filled
def create_main_window():
	global APP # this prevent APP being distroy after function exit

	#FIXME: BAD widgets layout
	# I need to invest in 'how to write a good tkinter'
	#
	# |----------------------------------|
	# |             status               |
	# |----------------------------------|
	# | source        | cout             |
	# |               -------------------|
	# |               | cerr             |
	# |----------------------------------|
	# | detail and controls              |
	# |----------------------------------|
	#
	# main window
	APP = tkinter.Tk()
	APP.title(TITLE)

	# reload button and status label frame
	status_frame = tkinter.Frame(APP, borderwidth=1)
	status_frame.pack(fill=tkinter.X)

	# main frame
	main_frame = tkinter.Frame(APP, borderwidth=1)
	main_frame.pack(fill=tkinter.BOTH, expand=1)

	# config reload button
	reload_config_btn = tkinter.Button(status_frame, text='reload config', command=reload_config)
	reload_config_btn.pack(side=tkinter.LEFT, padx=5, pady=5)

	# current status lable
	UIS['status'] = tkinter.StringVar()
	tkinter.Label(status_frame, textvariable=UIS['status']).pack(side=tkinter.LEFT)

	# left frame
	UIS['frame_left'] = tkinter.Frame(main_frame, borderwidth=1)
	UIS['frame_left'].pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=1)

	# right frame
	UIS['frame_right'] = tkinter.Frame(main_frame, borderwidth=1)
	UIS['frame_right'].pack(side=tkinter.RIGHT, fill=tkinter.BOTH, expand=1)

	#  source frame (for listbox)
	UIS['source_frame'] = tkinter.Frame(UIS['frame_left'], borderwidth=1)
	UIS['source_frame'].pack(fill=tkinter.BOTH, expand=1)

	#  source frame (for detail)
	UIS['source_detail'] = tkinter.Frame(UIS['frame_left'], borderwidth=1)
	UIS['source_detail'].pack(fill=tkinter.BOTH, expand=1)

	# source selection listbox
	UIS['sourcelistbox'] = tkinter.Listbox(UIS['source_frame'])

	reload_config()

	UIS['sourcelistbox'].bind('<<ListboxSelect>>', update_source_detail)
	UIS['sourcelistbox'].pack(fill=tkinter.BOTH, expand=1)
	return

# query for details of a source
def update_source_detail(event):
	logger.debug('update_source_detail: enter')

	global UIS # we modify UIS['cur_source'] here

	lbx = event.widget # sender widget is listbox
	index = int(lbx.curselection()[0]) # get current selection index (no multipleselction)
	selection = lbx.get(index) # selection value
#	print 'listbox selected index {}, value {}'.format(index, selection)

	logger.debug('CONFIGS: {0}'.format(CONFIGS))
	for w in UIS['source_detail'].winfo_children(): # clear source_detail frame
		w.destroy()

	cur_source = CONFIGS['source'][selection] # get source item from selection key
	UIS['cur_source'] = cur_source # update global current selected source
	cur_source['name'] = selection

	UIS['status'].set('{0} {1}'.format(selection, cur_source['version']))

	# show configure and build botton
	button_frame = tkinter.Frame(UIS['source_detail'], borderwidth=1)
	button_frame.pack(side=tkinter.TOP, fill=tkinter.X, expand=1)

	config_btn = tkinter.Button(button_frame, text='configure', command=config_source)
	config_btn.pack(side=tkinter.RIGHT, padx=2, pady=2)

	make_btn = tkinter.Button(button_frame, text='build', command=build_source)
	make_btn.pack(side=tkinter.RIGHT, padx=2, pady=2)

	# show configuration arguments in source detail listbox
	tkinter.Label(UIS['source_detail'], text=cur_source['config_cmd'] if 'config_cmd' in cur_source else 'N/A').pack()

	config_opts = tkinter.Listbox(UIS['source_detail'])
	if 'config_args' in cur_source: # check for valid key
		if cur_source['config_args']: # check for not empty
			for opt in cur_source['config_args']:
				for i in range(10): opt = os.path.expandvars(opt)
				config_opts.insert(tkinter.END, opt)
	config_opts.pack(fill=tkinter.BOTH, expand=1)
	config_opts.config(state=tkinter.DISABLED) # not support editing yet

	tkinter.Label(UIS['source_detail'], text=cur_source['build_cmd'] if 'build_cmd' in cur_source else 'N/A').pack()
	build_opts = tkinter.Listbox(UIS['source_detail'])
	if 'build_args' in cur_source:
		if cur_source['build_args']:
			for opt in cur_source['build_args']:
				for i in range(10): opt = os.path.expandvars(opt)
				build_opts.insert(tkinter.END, opt)
	build_opts.pack(fill=tkinter.BOTH, expand=1)
	build_opts.config(state=tkinter.DISABLED) # not support editing yet

	logger.debug('update_source_detail: exit')
	return

def build_source():
	logger.debug('build_source: enter')

	cur_source = UIS['cur_source'] # get current source to work with
	print 'building ... {}-{}'.format(cur_source['name'], cur_source['version'])

	source_name = cur_source['name'] + cur_source['version']
	# build_dir only valid after configurator called
	if 'build_dir' in cur_source:
		build_dir = cur_source['build_dir']
	else:
		print 'build_dir not valid'
		#UIS['status'] = 'N/A'
		return

	# if build_cmd is not provide we do nothing
	if('build_cmd' in cur_source):
		build_cmd = cur_source['build_cmd']
	else:
		return

	# if build_args is not provide we don't need to expand it
	build_args = []
	if 'build_args' in cur_source:
		raw_build_args= cur_source['build_args']

		# expand env in config_args
		if raw_build_args:
			for arg in raw_build_args:
				for i in range(10): arg = os.path.expandvars(arg)
				build_args.append(arg)
				#print 'bld ', arg

#	print 'source_name ', source_name
#	print 'build_dir ', build_dir
#	print 'build_cmd ', build_cmd
#	print 'build_args ', build_args

	ret = -1
	args = {}

	build_env = {}
	for key, val in os.environ.items():
		build_env[key] = val # get system envs (include common env by loadconfig())

	if ENV:
		print 'common envs'
		for key, val in ENV.items():
			print '  ', key, val

	source_env = cur_source['envs'] if 'envs' in cur_source else []
	if source_env:
		print 'source envs'
		for env in cur_source['envs']:
			key, val = env.split('=')
			for i in range(10):
				val = os.path.expandvars(val)
			build_env[key] = val # add source env to config_env
			print '  ', key, val
#	else:
#		print 'No source envs'

	print 'using builder "{}"'.format(build_cmd)
	args['task_name'] = source_name
	args['env'] = build_env
	args['working_dir'] = build_dir
	args['command'] = build_cmd
	args['arguments'] = build_args
	ret = do_exec(args)

	if ret == 0:
		print 'INFO: build success ({0})'.format(ret)
		UIS['status'].set('INFO: build success ({0})'.format(ret))
		print
	else:
		print 'ERROR: build failed ({0})'.format(ret) ;
		UIS['status'].set('ERROR: build failed ({0})'.format(ret))
		print

	logger.debug('build_source: exit')
	return


def config_source():
	logger.debug('config_source: enter')
	global UIS # we modify UIS['cur_source']

	cur_source = UIS['cur_source'] # get current source to work with
	print 'configuring ... {}{}'.format(cur_source['name'], cur_source['version'])

	source_name = cur_source['name'] + cur_source['version']
	source_dir = os.path.join(CONFIGS['common']['source_dir'], source_name)
	build_dir = os.path.join(CONFIGS['common']['build_dir'], source_name)
	for i in range(10):
		source_dir = os.path.expandvars(source_dir)
		build_dir = os.path.expandvars(build_dir)

	# if config_cmd is not provide we do nothing
	if('config_cmd' in cur_source):
		config_cmd = cur_source['config_cmd']
	else:
		return

	# if config_args is not provide we don't need to expand it
	config_args = []
	if 'config_args' in cur_source:
		raw_config_args= cur_source['config_args']

		# expand env in config_args
		if raw_config_args:
			for arg in raw_config_args:
				for i in range(10):
					arg = os.path.expandvars(arg)
				config_args.append(arg)
				#print 'cfg ', arg

	config_env = {}
	for key, val in os.environ.items():
		config_env[key] = val # get system envs (include common env by loadconfig())

	if ENV:
		print 'common envs'
		for key, val in ENV.items():
			print '  ', key, val

	source_env = cur_source['envs'] if 'envs' in cur_source else []
	if source_env:
		print 'source envs'
		for env in cur_source['envs']:
			key, val = env.split('=')
			for i in range(10):
				val = os.path.expandvars(val)
			config_env[key] = val # add source env to config_env
			print '  ', key, val
#	else:
#		print 'No source envs'

	# configuring selection by type of configurator
	ret = -1
	args = {}
	if config_cmd[0] == '.': # local configurator, e.g. ./configure, ./autogen.sh
		print 'using local configurator "{}"'.format(config_cmd)
		cur_source['build_dir'] = source_dir # pass build_dir to builder

		args['task_name'] = source_name
		args['env'] = config_env
		args['working_dir'] = source_dir
		args['command'] = config_cmd
		args['arguments'] = config_args
		ret = do_exec(args)
	else: # system wide, e.g. cmake
		print 'using system configurator "{}"'.format(config_cmd)
		if not os.path.exists(build_dir):
			os.makedirs(build_dir)
		cur_source['build_dir'] = build_dir # pass build_dir to builder

#		# this shoud be done in prebuid script
#		cmakecache = os.path.join(build_dir, 'CMakeCache.txt')
#		if os.path.exists(cmakecache):
#			print 'removing CMakeCache.txt'
#			os.remove(cmakecache)


#		print 'source_name ', source_name
#		print 'source_dir ', source_dir
#		print 'build_dir ', build_dir
#		print 'config_cmd ', config_cmd
#		print 'config_args ', config_args

		args['task_name'] = source_name
		args['env'] = config_env
		args['working_dir'] = build_dir
		args['command'] = config_cmd
		args['arguments'] = [source_dir] + config_args
		ret = do_exec(args)

	if ret == 0:
		print 'INFO: configure success ({0})'.format(ret)
		UIS['status'].set('INFO: configure success ({0})'.format(ret))
		print
	else:
		print 'ERROR: configure failed ({0})'.format(ret)
		UIS['status'].set('ERROR: configure failed ({0})'.format(ret))
		print

	logger.debug('config_source: exit')
	return

def initlogger(log_dir):
	print 'initlogger: log_dir=', log_dir
	if not os.path.exists(log_dir):
		os.makedirs(log_dir)

	hdlr=logging.FileHandler(os.path.join(log_dir, 'buildplace.py.log'))
	formatter=logging.Formatter('%(asctime)s %(levelname)s %(message)s')
	hdlr.setFormatter(formatter)
	logger.addHandler(hdlr)
	logger.setLevel(logging.DEBUG)

	logger.debug('initlogger exit')

'''
execute a process
WARNING: if shell=False any IO redirection in command migth fail
'''
def do_exec(args):
	for w in UIS['frame_right'].winfo_children():
		w.destroy()
	UIS['output_text'] = tkinter.Text(UIS['frame_right'])
	UIS['output_text'].pack(fill=tkinter.BOTH, expand=1)
	UIS['error_text'] = tkinter.Text(UIS['frame_right'])
	UIS['error_text'].pack(fill=tkinter.BOTH, expand=1)

	logger.debug('do_exec enter')
	logger.debug('do_exec: args {0}'.format(args))

	ts=time.clock()

	name = args['task_name'] # use for log naming
	cmd = args['command'] # the actual command without arguments eg. 'cmake'
	cmd_args = args['arguments'] # list of command argument eg. '['x', 'y', 'z']
	wd = args['working_dir'] # working directory
	if not os.path.exists(wd):
		print 'WARNING: working directory {} not exists. This migth cause configuring fail'.format(wd)
	env = args['env']

	log_dir = CONFIGS['common']['log_dir']
	cout_log=os.path.join(log_dir, name+ '-' + cmd.replace('./','') + '-cout.log')
	cerr_log=os.path.join(log_dir, name+ '-' + cmd.replace('./','') + '-cerr.log')

	cout=open(cout_log, 'wb')
	cerr=open(cerr_log, 'wb')

	command = [cmd] + cmd_args

	logger.info('command {0}'.format(command))
	print 'command ', command
#	print 'command_text', ' '.join(command)
	print 'wd ', wd
#	print 'env '
#	for key, val in env.items():
#		print '   {} - {}'.format(key, val)
	ret=subprocess.Popen(command, env=env, shell=False, cwd=wd, stdout=subprocess.PIPE, stderr=cerr)

	pad=' ' * (TERM_WIDTH + 5)
	while True:
		cout_line=ret.stdout.readline()
		if cout_line:
			#print pad, end='\r'
			#print '==', cout_line.decode('utf-8')[0:TERM_WIDTH].replace('\n','\r'), end='\r'
			UIS['status'].set(cout_line.decode('utf-8')[0:TERM_WIDTH])
			UIS['frame_right'].update_idletasks()
			cout.write(cout_line)
		else:
			break
	ret.wait()

	cout.close()
	cerr.close()


	cout=open(cout_log)
	for i in cout.readlines():
		UIS['output_text'].insert(tkinter.END, i)

	cerr=open(cerr_log)
	for i in cerr.readlines():
		UIS['error_text'].insert(tkinter.END, i)

	cerr.close()
	cout.close()
	if os.stat(cout_log).st_size == 0: os.remove(cout_log)
	if os.stat(cerr_log).st_size == 0: os.remove(cerr_log)

	te=time.clock() - ts
	if ret.returncode != 0:
		logger.error('cmd return %d time %s', ret.returncode, te)
	else:
		logger.info('cmd return %d time %s', ret.returncode, te)

	logger.debug('do_exec exit')
	return ret.returncode

# load yaml configuration
def loadconfig(filename=''):
	global ENV # this function modify global ENV
	config = {}

	# default buildplace.conf in this script folder if filename is not specify
	if(filename == ''):
		filename = os.path.dirname(os.path.abspath(__file__)) + '/build_source.conf'

	print 'using configfile ', filename

	try:
		config_file = open(filename)
		config = yaml.load(config_file)

		# set common env
		for env in config['common']['envs']:
			key, val = env.split('=')
			for i in range(10):
				val = os.path.expandvars(val)
			ENV[key] = val
			os.environ[key] = val # also pass common env to system (for used in var expansion)
			#print key,'=', val

		# expand all vars in common section, let system handle vars in command argument
		# this allow ~/xxx (or ${env}/xxx in future) in config file
		for i in range(10): #FIXME:ASSUMPTION: env should not nest this deep
			config['common']['source_dir']	= os.path.expandvars(config['common']['source_dir'])
			config['common']['build_dir']	= os.path.expandvars(config['common']['build_dir'])
			config['common']['log_dir']	= os.path.expandvars(config['common']['log_dir'])
	except IOError:
		print 'ERROR <IOError>: can\'t open configuration file \'{0}\''.format(os.path.join(os.getcwd(), filename))
		print '       Please check that file exists'
	except :
		print 'ERROR: can\'t open configuration file \'{0}\''.format(os.path.join(os.getcwd(), filename))
		print '       Please check that file exists and YAML-valid'
		print sys.exc_info()
	finally:
		config_file.close()
		#print config

	return config


# python trick for entering main when calling ./build_source.py from shell
if __name__ == '__main__': main()
