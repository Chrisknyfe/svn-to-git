#!/usr/bin/env python

import sys, os, shutil, subprocess, re, getopt, signal, shlex
from collections import namedtuple

#
# Input parameter related functions
#

usagestr = \
"""
Usage: python convert-to-git.py --root ROOTURL --repo SUBREPO [--remote REMOTEURL ...] DIRECTORY

Convert a subdirectory SUBREPO of an svn repository ROOTURL to a git repository at DIRECTORY.
Merge in all externals as if they had been developed in this directory 

Options:
  --root        Set the root repository URL to pull from
  --repo        Set the sub-repository of the root repository to pull form
  --remote      Add a remote mirror; If this script encounters an extern that points to one
                of these remotes, instead it will pull from the local repository specified 
                by --root.

""".strip()
def usage():
    print usagestr

def usagequit(message):
    print message
    usage()
    sys.exit(2)

def parseOptions():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['root=', 'repo=', 'remote=', 'users='])
    except getopt.GetoptError as err:
        usagequit(str(err))

    targetdir = None
    if len(args) == 0:
        targetdir = 'export'
    elif len(args) == 1:
        targetdir = args[0]
    else:
        usagequit("Too many arguments, only need one directory.")

    rootrepo = None
    repo = None
    remoterepos = []
    usersfile = None
    for o, a in opts:
        if o == '--root':
            rootrepo = a
        elif o == '--repo':
            repo = a
        elif o == '--remote':
            remoterepos.append(a)
        elif o == '--users':
            usersfile = a
    if rootrepo == None:
        usagequit("Please specify a root repository with --root")
    if repo == None:
        usagequit("Please specify a target sub-repository with --repo")
    if usersfile == None:
        usersfile = 'gitusers.txt'
    repo = rootrepo + repo
    return rootrepo, repo, remoterepos, targetdir, usersfile

def getUserLookup(filename):
    userLookup = {}
    with open(filename, 'r') as users:
        for line in users:
            line = line.strip()
            if line:
                tokens = line.split('=')
                if tokens and len(tokens) == 2:
                    userLookup[tokens[0].strip()] = tokens[1].strip()
                else:
                    raise RuntimeException("Couldn't parse user line: %s", line)
    return userLookup




#
# Shell command wrappers
#

class TimeoutException(Exception):
    pass
    
def timeoutHandler(signum, frame):
    raise TimeoutException()
    
    
def call(cmd, timeout = None):
    print cmd
    args = shlex.split(cmd.encode('utf8'))
    try:
        if timeout is not None:
            signal.signal(signal.SIGALRM, timeoutHandler)
            signal.alarm(timeout)
        p = subprocess.Popen(args)
        p.wait()
        if timeout is not None:
            signal.alarm(0)
    except TimeoutException:
        p.kill()
        print "command timed out"
        raise
    return p.returncode
def readcall(cmd, timeout = None):
    print cmd
    args = shlex.split(cmd.encode('utf8'))
    try:
        if timeout is not None:
            signal.signal(signal.SIGALRM, timeoutHandler)
            signal.alarm(timeout)
        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        stdoutdata, stderrdata = p.communicate()
        if timeout is not None:
            signal.alarm(0)
    except TimeoutException:
        p.kill()
        print "command timed out"
        raise
    if p.poll() != 0:
        raise subprocess.CalledProcessError(p.returncode, cmd)
    return stdoutdata
    

#
# History Queries
#

Revision = namedtuple("Revision", ["number", "user", "date", "log"])

def parseLogEntry(intext):
    text = intext.splitlines()

    # stupid dividers...
    while text[-1][0:8] == "--------" or not text[-1]:
        del text[-1]
    while text[0][0:8] == "--------" or not text[0]:
        del text[0]
    # Parse first line, matches something like the following:
    # r1234 | zbernal@vitalconnect.com | 2013-04-19 01:13:18 -0700 (Fri, 19 Apr 2013) | 3 lines
    match = re.search(r'^r([0-9]+) \| (.+) \| (.+) \(.+\).*', text[0])
    if match:
        number = int(match.groups()[0])
        svnuser = match.groups()[1]
        date = match.groups()[2]
        log = '\n'.join(text[1:])
        if svnuser not in userLookup:
            raise ValueError("No git user found for %s at line:\n%s" % (svnuser, text[0]))
        gituser = userLookup[svnuser]
        return Revision(number=number, user=gituser, date=date, log=log)
    else:
        raise RuntimeError("Not a valid log from 'svn log', cannot parse:\n%s" % text[0])

def getFirstRevision(repo):
    text = readcall("svn log -r0:HEAD --limit 1 %s" % repo)
    revision = parseLogEntry(text)
    return revision

def getLastRevision(repo):
    text = readcall("svn log --limit 1 %s" % repo)
    revision = parseLogEntry(text)
    return revision

def getRevision(repo, rev):
    text = readcall("svn log --limit 1 %s@%d" % (repo, rev) )
    revision = parseLogEntry(text)
    return revision

#
# Info queries
# 


def getRevisionInCwd():
    text = readcall("svn info")
    text = text.splitlines()
    for line in text:
        match = re.search(r'^Revision: (.*)$', line)
        if match:
            return int(match.groups()[0])
    raise ValueError("No Revision found in 'svn info'")

def getUrlInCwd():
    text = readcall("svn info")
    text = text.splitlines()
    for line in text:
        match = re.search(r'^URL: (.*)$', line)
        if match:
            return match.groups()[0]
    raise ValueError("No URL found in 'svn info'")

def getNodeKindForUrl(url, rev, pegrev):
    text = readcall("svn info -r %d %s@%d" % (rev, url, pegrev))
    text = text.splitlines()
    for line in text:
        match = re.search(r'^Node Kind: (.*)$', line)
        if match:
            return match.groups()[0]
    raise ValueError("No Node Kind found in 'svn info'")

def isThisPathDeleted(url, revnum):
    text = readcall("svn log -v -r %d %s" % (revnum, rootrepo))
    text = text.splitlines()
    for line in text:
        match = re.search(r'^ *D(.*)', line)
        if match:
            delitem = match.groups()[0].strip()
            if url.find(delitem) != -1:
                return True
    return False


#
# Handling Externs
#

Extern = namedtuple("Extern", ["object", "url", "rev", "pegrev", "isdirectory", "broken"])

def getExternals(revoffset = 0):
    revnum = getRevisionInCwd() + revoffset

    text = readcall("svn propget svn:externals -r %d -R" % (revnum))
    text = text.splitlines()

    currentParentDir = None
    for line in text:
        tokens = line.split()
        if tokens:
            try:
                # Parse the parent directory
                if tokens[1] == "-":
                    currentParentDir = tokens[0]
                    if re.search(r'^.*://', currentParentDir):
                        # Great, they gave us a URL when we needed a relative path. Let's remake the relative path.
                        url = getUrlInCwd()
                        currentParentDir = currentParentDir.replace(url, "")
                        if currentParentDir[0] == '/':
                            currentParentDir = currentParentDir[1:]
                    #print "currentParentDir:", currentParentDir
                    tokens = tokens[2:]

                if len(tokens) > 0: # sometimes we get a deleted extern that leaves this behind
                    # Parse extern line
                    childObject = None
                    externUrl = None
                    externRev = None
                    externPegrev = None
                    while len(tokens):
                        token = tokens.pop(0)
                        # URL
                        if re.search(r'^.+://', token):
                            match = re.search(r'^(.+)@(.+)', token)
                            if match:
                                externUrl = match.groups()[0]
                                externPegrev = int(match.groups()[1])
                            else:
                                externUrl = token
                            continue
                        # -rREVNUM
                        match = re.search(r'^-r(.+)', token)
                        if match:
                            externRev = int(match.groups()[0])
                            continue
                        # -r REVNUM
                        if token == '-r':
                            nexttoken = tokens.pop(0)
                            externRev = int(nexttoken)
                            continue
                        # local path
                        childObject = currentParentDir + "/" + token
                    assert externUrl != None and childObject != None

                    # Doctor the URL if we're using a local mirror of a remote repo
                    for remoterepo in remoterepos:
                        externUrl = externUrl.replace(remoterepo, rootrepo)

                    # Get the node kind for this extern, or find out if the extern even exists.
                    broken = False
                    try:
                        noderev = externRev
                        nodepegrev = externPegrev
                        noderev = externRev if externRev != None else revnum
                        nodepegrev = externPegrev if externPegrev != None else noderev
                        nodekind = getNodeKindForUrl(externUrl, noderev, nodepegrev)
                    except subprocess.CalledProcessError as e: 
                        print "Node kind lookup failed, marking this extern as broken."
                        broken = True
                        nodekind = None
                        
                    yield Extern(   object=childObject,
                                    url=externUrl,
                                    rev = externRev,
                                    pegrev = externPegrev,
                                    isdirectory=(nodekind == "directory"),
                                    broken=broken   )
            except:
                print "Here's the entire text:"
                print text
                print "Here's the current line:"
                print line
                print "Tokens:", tokens
                print "CWD:", os.getcwd()
                raise

def didExternalsChange(revnum):
    try:
        text = readcall("svn diff -c %d %s" % (revnum, rootrepo), timeout=30)
    except TimeoutException:
        return True
    if text.find("Modified: svn:externals") != -1:
        return True
    else:
        return False

def removeExternal(ex):
    if os.path.exists(ex.object):
        if ex.isdirectory or os.path.isdir(ex.object):
            shutil.rmtree(ex.object)
        else:
            os.remove(ex.object)

def updateExternalsTo(revnum):
    cwd = os.getcwd()

    # Make sure removed externals don't get kept.
    if didExternalsChange(revnum):
        print "Externals changed, clearing externals."
        for ex in getExternals(-1):
            removeExternal(ex)

    # Update all externals recursively.
    for ex in getExternals():
        print "Extern:", ex

        if ex.broken:
            removeExternal(ex)
        else:
            # Make sure the extern's url contains a revision number, if not provided.
            exrev = ex.rev if ex.rev != None else revnum
            expegrev = ex.pegrev if ex.pegrev != None else exrev

            if ex.isdirectory:
                if not os.path.exists(ex.object):
                    os.makedirs(ex.object)
                if os.path.exists( os.path.join(ex.object, '.svn') ):
                    retval = call("svn switch --ignore-externals -r %d %s@%d %s" % (exrev, ex.url, expegrev, ex.object))
                else:
                    retval = call("svn co --ignore-externals -r %d %s@%d %s" % (exrev, ex.url, expegrev, ex.object))
                if retval != 0:
                    raise RuntimeError("svn error")
                os.chdir(ex.object)
                updateExternalsTo(revnum)
                os.chdir(cwd)
            else:
                if os.path.exists(ex.object):
                    os.remove(ex.object)
                if call("svn export -r %d %s@%d %s" % (exrev, ex.url, expegrev, ex.object))!= 0:
                    raise RuntimeError("svn error")

#
# Helper Functions
#

def deleteAllContentInCwd():
    for item in os.listdir(os.getcwd()):
        if not item in ['.git', '.svn']:
            call("rm -fr %s" % item)
            
#============================================================#

#
# Parse input parameters
#      
            
rootrepo, repo, remoterepos, targetdir, usersfile = parseOptions()
userLookup = getUserLookup(usersfile)

#
# Create our new git repo
#

if not os.path.exists(targetdir):
    os.mkdir(targetdir)
os.chdir(targetdir)

if not os.path.exists('.git'): 
    call("git init")
    with open(".git/info/exclude", 'a') as gitignore:
        gitignore.write("**/.svn/**\n")
        gitignore.write(".commitmessage\n")

#
# Figure out which revisions to replay
#

revnumbers = None
if os.path.exists('.git/info/progress'):
    startrevnum = 0
    with open('.git/info/progress', 'r') as gitprogress:
        startrevnum = int(gitprogress.read())
    lastrev = getLastRevision(repo)
    revnumbers = xrange(startrevnum, lastrev.number + 1)
    print "Continuing from rev %d to rev %d." % (startrevnum ,lastrev.number)
else:
    firstrev = getFirstRevision(repo)
    lastrev = getLastRevision(repo)
    revnumbers = xrange(firstrev.number, lastrev.number + 1)
    print "Starting from scratch from rev %d to rev %d" % (firstrev.number, lastrev.number)


#
# replay every svn revision on the new git repo
#

# BCS!
# revision 106, Pain was renamed to BandageCommServer # just a file move, handled
# revision 110, project pain was moved to /trunk/src/BandageCommServer # handled
# revision 1578, extern/crc is added. # handled
# revision 2852, extern/crc is removed. # handled
# revision 3126, BandageCommServer can't be found. WTF? It's there!
# revision 3384, BandageCommServer was removed.
# revision 3385, BandageCommServer was brought back. # need to fix tree conflict here
# revision 5094, specified '-r REV URL@PEGREV' extern form
# revision 9000, sensor_stream has a file extern "vc_queue.h" # handled

#testpoint = 3000
#revnumbers = xrange(testpoint, lastrev.number)
#revnumbers = xrange(testpoint, testpoint+400)


def updateProjectRootToRevision(rev):
    # Update project root to revision
    if os.path.exists('.svn'):
        retval = call("svn switch --ignore-externals --accept theirs-full -r %d %s@%d" % (rev.number, repo, rev.number))
    else:
        retval = call('svn co --ignore-externals -r %d %s@%d .' % (rev.number, repo, rev.number))
    if retval != 0:
        thispathwasdeleted = isThisPathDeleted(repo, rev.number)
        if thispathwasdeleted:
            print "Oh, this path was deleted! Someone forgot how to merge... Remove everything for now."
            deleteAllContentInCwd()
            retval = 0

    if retval != 0:
        # Let's try not specifying a pegrev. This will probably help in the case that the source for this object
        # came from another location.
        if os.path.exists('.svn'):
            retval = call("svn switch --ignore-externals --accept theirs-full -r %d %s" % (rev.number, repo))
        else:
            retval = call('svn co --ignore-externals -r %d %s .' % (rev.number, repo))
    return retval


for revnum in revnumbers:
    print "\n-------- Replaying revision %d --------\n" % revnum
    rev = getRevision(rootrepo, revnum)

    print rev

    thispathwasdeleted = False

    retval = updateProjectRootToRevision(rev)
    if retval != 0:
        # nuke it and try again, in case of conflicts.
        deleteAllContentInCwd()
        if os.path.exists('.svn'):
            call("rm -fr .svn")
        retval = updateProjectRootToRevision(rev)
    
    if retval != 0:
        raise RuntimeError("svn error")
    elif not thispathwasdeleted:
        updateExternalsTo(rev.number)

    call("git add -u")
    call("git add --all .")
    with open(".commitmessage", 'w') as commitmessage:
        commitmessage.write("%s\n\nExported from %s@%s" % (rev.log, repo, rev.number))
    call('git commit --author="%s" --date="%s" --file=.commitmessage' % (rev.user, rev.date))
    os.remove(".commitmessage")

    with open(".git/info/progress", 'w') as gitprogress:
        gitprogress.write(str(rev.number))

# Filter the history so its dates are correct.
call("git filter-branch -f --env-filter 'GIT_COMMITTER_DATE=$GIT_AUTHOR_DATE; export GIT_COMMITTER_DATE'")

