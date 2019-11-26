#!/usr/bin/env python
# encoding: utf-8
'''
manage_files.py

@author:     Piotr Nikiel <piotr@nikiel.info>
@author:     Damian Abalo Miron <damian.abalo@cern.ch>

@copyright:  2015 CERN

@license:
Copyright (c) 2015, CERN, Universidad de Oviedo.
All rights reserved.
Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

@contact:    quasar-developers@cern.ch
'''

import errno

try:
    import sys
    import os
    import platform
    import os.path
    import subprocess
    import traceback
    from optparse import OptionParser
    import hashlib
    import version_control_interface

    # lxml for getting a list of defined classes in Design file
    from lxml import etree

    import shutil  # for copying files, etc
    import glob


except Exception as e:
    print("Apparently you dont have all required python modules to run this program.")
    print("For SLC6 system, please execute:")
    print("	  sudo yum install pysvn python-lxml ")
    print("For another operating system, contact piotr@nikiel.info for assistance in setting up this project")
    raise e


verbose=False
ask=False

def yes_or_no(question):
    while True:
        print(question+' type y or n; then enter   ')
        sys.stdout.flush()
        yn = raw_input()
        if yn in ['y','n']:
            return yn



def get_list_classes(design_file_name):
    output=[]
    f = open(design_file_name,'r')
    tree = etree.parse(f)
    classes = tree.findall('{http://cern.ch/quasar/Design}class')
    for c in classes:
        d={'name':c.get('name')}
        d['has_device_logic']=(len(c.findall('{http://cern.ch/quasar/Design}devicelogic'))>0)
        output.append(d)
    return output



def get_key_value_pairs(options, allowed_keys, dictionary):
    pairs=[]
    chunks = options.split(",")
    for o in chunks:
        o=o.replace(' ','')
        if o=="":
            continue
        elif o.find('=')>=0:
            name=o.split('=')[0]
            if not name in allowed_keys:
                raise Exception ('key: '+name+' is not in list of allowed keys:'+str(allowed_keys))
            val=o.split('=')[1]
            dictionary[name]=val
        else:
            if not o in allowed_keys:
                raise Exception ('key: '+o+' is not in list of allowed keys:'+str(allowed_keys))
            dictionary[o]=None

def export_key_value_pairs(keys,dictionary):
    output=""
    for k in keys:
        if k in dictionary:
            output=output+k
            if dictionary[k]!=None:
                output=output+"="+str(dictionary[k])
            output=output+","
    return output

class File(dict):
    allowed_keys=['must_exist','must_be_versioned','md5','install','always_autogenerated','deprecated']
    def __init__(self,textLine,directory):
        chunks = textLine.split()
        if chunks[0] != 'File':
            raise Exception ("A textline given to File() doesnt start with File: "+chunks[0])
        self['path']=directory+chunks[1]
        self['name']=chunks[1]
        get_key_value_pairs(' '.join(chunks[2:]), File.allowed_keys, self)


    def path(self):
        return self['path']
    def must_be_versioned(self):
        return 'must_be_versioned' in self

    def must_be_md5_checked(self):
        return 'md5' in self
    def must_exist(self):
        return 'must_exist' in self
    def deprecated(self):
        return 'deprecated' in self

    @staticmethod
    def compute_md5(file_name):
        # Piotr: used the nice recipe from https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file
        hash_md5 = hashlib.md5()
        with open(file_name, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    
    def check_md5(self):
        if verbose: print("---> Checking md5 of file: "+self.path())
        if not os.path.isfile(self.path()):
            return ['Cant checksum because the file doesnt exist: '+self.path()]
        else:
            md5 = self.compute_md5(self.path())
            if md5!=self['md5']:
                return ['MD5 Failure at file: '+self.path()+' md5_obtained='+md5+' md5_expected='+self['md5']]
            else:
                return []


    def check_consistency(self, vci):
        if verbose: print("--> check_consistency called on File "+self.path())
        problems=[]
        if self.must_exist():
            if not os.path.isfile(self.path()):
                problems.append('File must exist but it doesnt: '+self.path())
        # check versioning
        if self.must_be_versioned():
            # this applies only if file exists
            if os.path.isfile(self.path()):
                if verbose: print("----> checking if versioned: "+self.path())
                if not vci.is_versioned(self.path()):
                    if ask:
                        print("File is not versioned: "+self.path())
                        yn = yes_or_no("Do you want to fix that now?")
                        if yn == 'y':
                            vci.add_to_vc(self.path())
                        else:
                            problems.append('File not versioned: '+self.path())
                    else:
                        problems.append('File not versioned: '+self.path())

        if self.must_be_md5_checked():
            problems.extend(self.check_md5())
        if self.deprecated():
            if os.path.isfile(self.path()):
                if ask:
                    print("File is deprecated: "+self.path())
                    yn = yes_or_no("Do you want to fix that now?")
                    if yn == 'y':
                        if vci.is_versioned(self.path()):
                            print('Attempting delete with your version control system: you will have to commit afterwards!')
                            vci.remove_from_vc(self.path())
                        else:
                            print('Deleting deprecated file: '+self.path())
                            os.remove(self.path())
                            pass
                    else:
                        problems.append('This file is deprecated, please remove it: '+self.path())
                else:
                    problems.append('This file is deprecated, please remove it: '+self.path())

        return problems


    
    def make_md5(self):
        self['md5'] = self.compute_md5(self.path())

        
        
    def make_text_line(self):
        s="File "+os.path.basename(self.path())+" "+export_key_value_pairs(File.allowed_keys, self)
        return s


class Directory(dict):
    allowed_keys=['install']
    def __init__(self,basename,textLine):
        self['files']=[]
        self['name']=basename
        chunks = textLine.split()
        if chunks[0] != 'Directory':
            raise Exception ("A textline given to Directory() doesnt start with Directory: "+chunks[0])
        get_key_value_pairs(' '.join(chunks[2:]), Directory.allowed_keys, self)
    def add_file(self,file):
        self['files'].append(file)
    def make_text(self):
        s="Directory "+self['name']+" "+export_key_value_pairs(Directory.allowed_keys, self)+"\n"
        for f in self['files']:
            s=s+f.make_text_line()+"\n"
        return s
    def check_consistency(self, vci):
        problems=[]
        for f in self['files']:
            problems.extend(f.check_consistency(vci))
        return problems

def check_consistency(directories, project_directory, vci):
    # to the files loaded from files.txt we have to add files that would be generated for defined classes
    classes = get_list_classes(project_directory+os.path.sep+"Design"+os.path.sep+"Design.xml")

    directory_Device_include = None
    directory_Device_src = None
    directory_AddressSpace_include = None
    directory_AddressSpace_src = None
    for d in directories:
        if d['name']=="Device/include":
            directory_Device_include = d
        elif d['name']=="Device/src":
            directory_Device_src = d
        elif d['name']=="AddressSpace/include":
            directory_AddressSpace_include = d
        elif d['name']=="AddressSpace/src":
            directory_AddressSpace_src = d

    for c in classes:
        if c['has_device_logic']:
            directory_Device_include.add_file(File("File D"+c['name']+".h must_exist,must_be_versioned", project_directory+os.path.sep+"Device"+os.path.sep+"include"+os.path.sep))
            directory_Device_src.add_file(File("File D"+c['name']+".cpp must_exist,must_be_versioned", project_directory+os.path.sep+"Device"+os.path.sep+"src"+os.path.sep))

    problems=[]



    for d in directories:
        problems.extend(d.check_consistency(vci))
    return problems


def scan_dir(dir):
    files=[]
    contents = os.listdir(dir)
    for c in contents:
        full_path=dir+os.path.sep+c
        if os.path.isfile(full_path):
            files.append(full_path)
        elif os.path.isdir(full_path):
            if c!=".svn" and c!=".git":
                files.extend (scan_dir(full_path))
        else:
            print('skipped: '+full_path+' which is neither file nor directory')
    return files

def check_uncovered(directories,project_directory):
    # build a list of all covered files
    all_files=scan_dir(project_directory)
    for d in directories:
        for f in d['files']:
            if f.path() in all_files:
                all_files.remove(f.path())
    print("uncovered files:")
    for f in all_files:
        print(f)





def load_file(file_name,project_directory):
    ''' Returns list of directories '''
    line_no=0
    directories=[]
    f=open(file_name,'r')
    try:
        for line in f:
            line_no = line_no+1
            line=line.replace('\n','')
            if len(line)<1:
                continue
            if line[0]=='#':
                continue
            chunks = line.split()
            if len(chunks)<1:
                continue  # skip an empty line
            if chunks[0]=='Directory':
                current_directory = Directory( chunks[1], line )
                if chunks[1]=='.':
                    current_subdirectory=''
                else:
                    current_subdirectory=chunks[1]
                directories.append(current_directory)
            elif chunks[0]=='File':
                p=''
                if current_subdirectory!='':
                    p=project_directory+os.path.sep+current_subdirectory+os.path.sep
                else:
                    p=project_directory+os.path.sep
                fd=File(line,p)
                current_directory.add_file(fd)
            else:
                raise Exception ('First word of line: '+chunks[0]+' unknown')

    except Exception as e:
        print("The exception was thrown while processing line "+str(line_no))
        raise e

    return directories



def create_release(directories):
    global problems
    '''Command line options.'''

    s= "# © Copyright CERN, 2015. All rights not expressly granted are reserved.\n"
    s+="# \n"
    s+="# This file lists files of Quasar which should be installed in the target project.\n"
    s+="# Please note that this file is a derivative of original_files.txt with md5 checksums applied.\n"
    for d in directories:
        for f in d['files']:
            if f.must_be_md5_checked():
                f.make_md5()
        s=s+d.make_text()
    f=open('FrameworkInternals' + os.path.sep + 'files.txt','w')
    f.write(s)
    print('file files.txt was created')

def perform_installation(directories, source_directory, target_directory):
    if not os.path.isdir(target_directory):
        print('given target_directory='+target_directory+' doesnt exist or is not a directory')
        return False
    for d in directories:
        source_dir_path = source_directory+os.path.sep+d['name']
        target_dir_path = target_directory+os.path.sep+d['name']
        if 'install' in d:
            dir_action = d['install']
            if dir_action=='create':
                if not os.path.isdir(target_dir_path):
                    print('Creating directory '+target_dir_path)
                    os.mkdir(target_dir_path)
            else:
                raise Exception ('directory '+d['name']+' install='+dir_action+' is not valid')
        for f in d['files']:
            source_file_path = source_dir_path+os.path.sep+f['name']
            target_file_path = target_dir_path+os.path.sep+f['name']
            print("at file="+f.path())
            if 'install' in f:
                file_action = f['install']
                if file_action=='overwrite':
                    if not os.path.isfile(target_file_path):
                        print('Copying '+source_file_path+' -> '+target_file_path)
                        shutil.copy2(source_file_path,  target_file_path)
                    else:
                        print('Overwriting: '+target_file_path)
                        shutil.copy2(source_file_path,  target_file_path)
                elif file_action=='ask_to_merge':
                    # if the target file doesnt exist, just copy it
                    if not os.path.isfile(target_file_path):
                        print('Copying '+source_file_path+' -> '+target_file_path)
                        shutil.copy2(source_file_path,  target_file_path)
                    else:
                        # maybe the files are the same and it is not needed to merge ??
                        if os.system('diff '+source_file_path+' '+target_file_path)==0:
                            print('Files the same; merging not needed')
                        else:
                            print('Filed differ; merging needed')
                            merge_val=os.system('kdiff3 -o '+target_file_path+' '+source_file_path+' '+target_file_path)
                            print('Merge tool returned: '+str(merge_val))
                            if merge_val!=0:
                                yn=yes_or_no('Merge tool returned non-zero, wanna continue?')
                                if yn=='n':
                                    sys.exit(1)
                elif file_action=='copy_if_not_existing':
                    if not os.path.isfile(target_file_path):
                        print('Copying '+source_file_path+' -> '+target_file_path)
                        shutil.copy2(source_file_path,  target_file_path)
                elif file_action=='dont_touch':
                    pass
                else:
                    raise Exception ( 'install='+file_action+' not valid' )


    return True


def project_setup_svn_ignore(project_directory):

    cmd="svn propset svn:ignore -F .gitignore -R "+project_directory
    print('Will call: '+cmd)
    os.system(cmd)



def check_file_for_mtime ( design_mtime, p, project_directory, type, c ):
    if not os.path.isfile(p):
        print('*** ERROR: Following device file doesnt exist:')
        print('  '+p)
        print('  Without it, the build will most certainly fail.')
        yn = yes_or_no('Would you like to generate an empty stub of this class?')
        if yn == 'y':
            print('  Trying to generate the empty stub')
            what=''
            if type=='h':
                what='Header'
            elif type=='cpp':
                what='Body'
            else:
                raise Exception('Internal error -- type not in enumeration:'+str(type))
            os.system('cd '+project_directory+'; cd Device; ./generateDevice'+what+'.sh '+c['name'])

    else:
        file_mtime = os.path.getmtime( p )
        if design_mtime > file_mtime:
            print('*** WARNING: Following device file is older than your design file:')
            print('  '+p)
            print('  If build goes bananas, this could be one of the reasons.')



def design_vs_device(project_directory):
    # get modification time of the file
    design_mtime = os.path.getmtime(project_directory+os.path.sep+'Design'+os.path.sep+'Design.xml')
    # now run over all human-managed device files
    classes = get_list_classes(project_directory+os.path.sep+"Design"+os.path.sep+"Design.xml")
    for c in classes:
        if c['has_device_logic']:
            check_file_for_mtime( design_mtime, project_directory+os.path.sep+'Device'+os.path.sep+'src'+os.path.sep+'D'+c['name']+'.cpp', project_directory, 'cpp', c)
            check_file_for_mtime( design_mtime, project_directory+os.path.sep+'Device'+os.path.sep+'include'+os.path.sep+'D'+c['name']+'.h', project_directory, 'h', c)
    pass


#manage files API starts here
def mfCheckConsistency(param=None):
    """Checks the consistency of the project, checking that all the files that must exist do exist, everything is in svn and the md5 keys are correct."""
    vci = version_control_interface.VersionControlInterface('.')
    global svnClient

    global ask
    if param == "--ask":
        ask = True
    directories = load_file('FrameworkInternals' + os.path.sep + 'files.txt', os.getcwd())
    problems=check_consistency(directories, os.getcwd(), vci)
    check_uncovered(directories,os.getcwd())
    if len(problems)>0:
        print("I've found this consistency problems (#problems="+str(len(problems))+")")
        for p in problems:
            print(p)
    else:
        print("No problems found.")

def mfCreateRelease(context):
    """Upgrades files.txt with the contents of original_files.txt. Expert command, only to be used by developers of the framework when creating a new release"""
    os.chdir(context['projectSourceDir'])
    directories = load_file(os.path.join('FrameworkInternals','original_files.txt'), os.getcwd())
    create_release(directories)

def mfInstall(sourceDirectory, targetDirectory):
    """Installs or upgrades the framework in a given directory

    Keyword arguments:
    sourceDirectory -- The directory where the framework is currently
    targetDirectory -- The target directory where the framework will be installed or upgraded
    """
    directories = load_file('FrameworkInternals' + os.path.sep + 'files.txt', os.getcwd())
    perform_installation(directories, sourceDirectory, targetDirectory)

def mfSetupSvnIgnore():
    """Setups the .svnignore hidden file, so the generated files will be ignored in your svn repository."""
    project_setup_svn_ignore(os.getcwd())

def mfCheckSvnIgnore():
    """Checks that the .svnignore hidden file is properly set up to ignore the generated files in your repository."""
    check_svn_ignore_project(os.getcwd())

def mfDesignVsDevice():
    """Checks if the device files are outdated (By comparing with design), and hence if they should be regenerated."""
    design_vs_device(os.getcwd())

def copyIfNotExists(src, dst):
    if not os.path.exists( os.path.dirname(dst) ):
        print('File [{0}] copy rejected - destination directory does not exist [{1}]'.format(os.path.basename(src), os.path.dirname(dst)))
        return

    yepCopyFile = False
    if not os.path.exists(dst):
        yepCopyFile = True
    else:
        yepCopyFile = ( 'y' == yes_or_no('binary directory file [{0}] already exists, do you want to replace it with source directory file [{1}]? Contents *will* be overwritten.'.format(dst, src)) )

    if yepCopyFile:
        print('Copying source directory file [{0}] to binary directory file {1}'.format(os.path.basename(src), dst))
        shutil.copyfile(src, dst)
    else:
        print('Skipped: copying source file [{0}]: copy rejected by user'.format(os.path.basename(src)))

def symlinkIfNotExists(src, dst):
    try:
        os.symlink(src, dst)
        print('Symlinked {0} as {1}'.format(src, dst))
    except OSError as e:
        if e.errno == errno.EEXIST:
            print('Skipped {0} because: target already exists'.format(src))
        else:
            raise e

def symlinkRuntimeDeps(context, wildcard=None):
    # for windows runtime deps are copied; this avoids requiring elevated privileges (windows symlink requires admin rights)
    linkerFunction = copyIfNotExists if platform.system().lower() == 'windows' else symlinkIfNotExists
    if wildcard is None:
        yn = yes_or_no('No argument provided, will symlink ServerConfig.xml and all config*.xml files, OK?')
        if yn == 'n':
            return
        linkerFunction(
                os.path.join(context['projectSourceDir'], 'bin', 'ServerConfig.xml'),
                os.path.join(context['projectBinaryDir'], 'bin', 'ServerConfig.xml'))
        config_files = glob.glob(os.path.join(context['projectSourceDir'], 'bin', 'config*.xml'))
        for config_file in config_files:
            linkerFunction(config_file, os.path.join(context['projectBinaryDir'], 'bin', os.path.basename(config_file)))
    else:
        config_files = glob.glob(os.path.join(context['projectSourceDir'], 'bin', wildcard))
        print('Matched {0} files'.format(len(config_files)))
        for config_file in config_files:
            linkerFunction(config_file, os.path.join(context['projectBinaryDir'], 'bin', os.path.basename(config_file)))
