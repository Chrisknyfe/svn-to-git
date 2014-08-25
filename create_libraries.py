#!/usr/bin/env python

# Clone all of our SVN projects to git repos, then merge them into a "libraries" git repo.

import os, subprocess, shlex

def call(cmd):
    print cmd
    args = shlex.split(cmd.encode('utf8'))
    return subprocess.call(args)
    
def readcall(cmd):
    print cmd
    args = shlex.split(cmd.encode('utf8'))
    return subprocess.check_output(args)

def createlibraries(    rootrepo,
                        libraries,
                        targetdir='libraries_build',
                        remoterepos=[],
                        gitfilterprefix=None,
                        gitcherrysort=None,
                        gitusers=None,
                        converttogit=None ):
    if not gitfilterprefix:
        gitfilterprefix = os.path.abspath('git_filter_prefix.sh')
    if not gitcherrysort:
        gitcherrysort = os.path.abspath('git_cherry_sort.sh')
    if not gitusers:
        gitusers = os.path.abspath('gitusers.txt')
    if not converttogit:
        converttogit = os.path.abspath('convert_to_git.py')

    # Make a subfolder to contain all these wild shenanigans
    if not os.path.exists(targetdir):
        os.mkdir(targetdir)
    os.chdir(targetdir)
    rootleveldir = os.getcwd()

    for modname, url in libraries.iteritems():
        os.chdir(rootleveldir)
        dirname = os.path.abspath("export_" + modname)
        outputdirname = os.path.abspath("filtered_" + modname)
        
        # Export each library from the svn repo
        print "\n-- Exporting library %s --\n" % modname
        cmdstr = "%s --no-externals --root %s --repo %s --users %s" % (converttogit, rootrepo, url, gitusers)
        for remote in remoterepos:
            cmdstr += " --remote %s" % remote
        cmdstr += " %s" % dirname
        retval = call(cmdstr)
        if retval != 0:
            raise RuntimeError("convert_to_git error")
            
        # Copy the exported library somewhere else to be filtered.
        if os.path.exists(outputdirname):
            call("rm -rf %s" % outputdirname)
        call("cp -R %s %s" % (dirname, outputdirname))

        # Filter each library's commits into a subfolder
        print "\n-- Filtering library %s --\n" % modname
        os.chdir(outputdirname)
        retval = call("%s %s" % (gitfilterprefix, modname))
        if retval != 0:
            raise RuntimeError("git_filter_prefix error")
            
            
    # Make a "libraries" git repo that we'll fill with these libraries
    os.chdir(rootleveldir)
    print "\n-- Creating \"libraries\" repo --\n"
    librariesrepo = os.path.abspath('libraries') 
    if os.path.exists(librariesrepo):
        call("rm -rf %s" % librariesrepo)
        
    os.mkdir(librariesrepo)
    os.chdir(librariesrepo)
    call("git init")
    with open(".gitignore", 'a') as gitignore:
        gitignore.write("**/.svn/**\n")
    call("git add .gitignore")
    call("git commit -m 'Create libraries repo'")

    # Pull each library
    for modname, url in libraries.iteritems():
        print "\n-- Pulling library %s --\n" % modname
        os.chdir(rootleveldir)
        dirname = os.path.abspath("filtered_" + modname)
        os.chdir(librariesrepo)
        retval = call("git pull --no-edit %s" % (dirname))
        if retval != 0:
            raise RuntimeError("git pull error")

    # Merge the git repo
    print "\n-- Sorting and Filtering \"libraries\" repo --\n"
    os.chdir(librariesrepo)
    retval = call(gitcherrysort)
    if retval != 0:
        raise RuntimeError("git_cherry_sort error")
        
if __name__ == '__main__':
    rootrepo = "file:///home/chrisknyfe/migration/localsvn"

    libraries= {
                "common":                   "/trunk/src/common/",
                "algorithms":               "/trunk/src/algorithms/",
                "packet_protocol":          "/trunk/src/packet_protocol/",
                "toolbox":                  "/trunk/toolbox/",
                }
                
    createlibraries(rootrepo, libraries)
            
        
