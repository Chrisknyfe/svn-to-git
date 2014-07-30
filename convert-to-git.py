#!/usr/bin/env python

import sys, os, shutil, subprocess, re, getopt, signal, shlex, functools
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
        opts, args = getopt.getopt(sys.argv[1:], '', ['root=', 'repo=', 'remote=', 'users=', 'ancestry'])
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
    checkancestry = False
    for o, a in opts:
        if o == '--root':
            rootrepo = a
        elif o == '--repo':
            repo = a
        elif o == '--remote':
            remoterepos.append(a)
        elif o == '--users':
            usersfile = a
        elif o == '--ancestry':
            checkancestry = True
            
    if rootrepo == None:
        usagequit("Please specify a root repository with --root")
    if repo == None:
        usagequit("Please specify a target sub-repository with --repo")
    if usersfile == None:
        usersfile = 'gitusers.txt'
    repo = rootrepo + repo
    return rootrepo, repo, remoterepos, targetdir, usersfile, checkancestry

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
    def __init__(self, cmd, seconds):
        Exception.__init__(self, cmd, seconds)
        self.cmd = cmd
        self.seconds = seconds
    def __str__(self):
        return "Command '%s' timed out after %d seconds." % (self.cmd, self.seconds)
    
class CalledProcessError(subprocess.CalledProcessError):
    """A subprocess.CalledProcessError that keeps stdout and stderr data separate."""
    def __init__(self, returncode, cmd, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr
        if not stdout:
            stdout = ""
        if not stderr:
            stderr = ""
        subprocess.CalledProcessError.__init__(self, returncode, cmd, stdout + stderr)
    def __str__(self):
        return subprocess.CalledProcessError.__str__(self) + ':\n%s' % self.stderr
    
def timeoutHandler(cmd, seconds, signum, frame):
    raise TimeoutException(cmd, seconds)
    
def call(cmd, timeout = None, printcommand=True):
    if printcommand:
        print cmd
    args = shlex.split(cmd.encode('utf8'))
    try:
        if timeout is not None:
            handler = functools.partial(timeoutHandler, cmd, timeout)
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(timeout)
        p = subprocess.Popen(args)
        p.wait()
        if timeout is not None:
            signal.alarm(0)
    except TimeoutException as e:
        p.kill()
        print e
        raise
    return p.returncode
    
def readcall(cmd, timeout = None, printcommand=True, printstdout=False, printstderr=True):
    if printcommand:
        print cmd
    args = shlex.split(cmd.encode('utf8'))
    try:
        if timeout is not None:
            handler = functools.partial(timeoutHandler, cmd, timeout)
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(timeout)
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdoutdata, stderrdata = p.communicate()
        if timeout is not None:
            signal.alarm(0)
    except TimeoutException as e:
        p.kill()
        print e
        raise
    if printstdout:
        print stdoutdata
    if printstderr:
        print >> sys.stderr, stderrdata
    if p.poll() != 0:
        raise CalledProcessError(p.returncode, cmd, stdoutdata, stderrdata)
    return stdoutdata, stderrdata
    

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
    text, errtext = readcall("svn log -r0:HEAD --limit 1 %s" % repo)
    revision = parseLogEntry(text)
    return revision

def getLastRevision(repo):
    text, errtext = readcall("svn log --limit 1 %s" % repo)
    revision = parseLogEntry(text)
    return revision

def getRevision(rev):
    text, errtext = readcall("svn log -r %d --limit 1 %s" % (rev, rootrepo) )
    revision = parseLogEntry(text)
    return revision

#
# Info queries
# 


def getRevisionInCwd():
    text, errtext = readcall("svn info")
    text = text.splitlines()
    for line in text:
        match = re.search(r'^Revision: (.*)$', line)
        if match:
            return int(match.groups()[0])
    raise ValueError("No Revision found in 'svn info'")

def getUrlInCwd():
    text, errtext = readcall("svn info")
    text = text.splitlines()
    for line in text:
        match = re.search(r'^URL: (.*)$', line)
        if match:
            return match.groups()[0]
    raise ValueError("No URL found in 'svn info'")

def getUrlForRepoAtRevision(repo, rev=None, peg=None):
    assert rev != None or peg != None
    if rev == None:
        text, errtext = readcall("svn info %s@%d" % (repo, peg), printcommand=False, printstderr=False)
    elif peg == None:
        text, errtext = readcall("svn info -r %d %s" % (rev, repo), printcommand=False, printstderr=False)
    else:
        text, errtext = readcall("svn info -r %d %s@%d" % (rev, repo, peg), printcommand=False, printstderr=False)
    text = text.splitlines()
    for line in text:
        match = re.search(r'^URL: (.*)$', line)
        if match:
            return match.groups()[0]
    raise ValueError("No URL found in 'svn info'")


def getNodeKindForUrl(url, rev, pegrev):
    text, errtext = readcall("svn info -r %d %s@%d" % (rev, url, pegrev))
    text = text.splitlines()
    for line in text:
        match = re.search(r'^Node Kind: (.*)$', line)
        if match:
            return match.groups()[0]
    raise ValueError("No Node Kind found in 'svn info'")

def isThisPathDeleted(url, revnum):
    text, errtext = readcall("svn log -v -r %d %s" % (revnum, rootrepo))
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

def getExternals(toplevelrevnum):
    revnum = getRevisionInCwd()
    text, errtext = readcall("svn propget svn:externals -r %d -R" % (revnum))
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
                        if currentParentDir and currentParentDir[0] == '/':
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
                        if currentParentDir:
                            childObject = currentParentDir + "/" + token
                        else:
                            childObject = token
                            
                    assert externUrl != None and childObject != None

                    # Doctor the URL if we're using a local mirror of a remote repo
                    for remoterepo in remoterepos:
                        externUrl = externUrl.replace(remoterepo, rootrepo)
                        
                    # Set the pegrev to the top-level rev. We want to get this extern
                    # as if we were checking it out on the day of this commit.
                    if externPegrev == None:
                        externPegrev = toplevelrevnum
                    # If operative rev isn't specified, doesn't hurt to set it to the
                    # pegrev.
                    if externRev == None:
                        externRev = externPegrev

                    # Get the node kind for this extern, or find out if the extern even exists.
                    broken = False
                    try:
                        nodekind = getNodeKindForUrl(externUrl, externRev, externPegrev)
                    except CalledProcessError as e:
                        if e.stderr.find("non-existent in revision") != -1:
                            print "Extern can't be found at this location."
                        else:
                            raise
                        broken = True
                        nodekind = None
                        
                    yield Extern(   object=childObject,
                                    url=externUrl,
                                    rev = externRev,
                                    pegrev = externPegrev,
                                    isdirectory=(nodekind == "directory"),
                                    broken=broken   )
            except:
                print "-------- Getting Externals --------"
                print "Here's the entire text:"
                print text
                print "Here's the current line:"
                print line
                print "Tokens:", tokens
                print "CWD:", os.getcwd()
                print "-----------------------------------"
                raise

def didExternalsChange(revnum):
    try:
        text, errtext = readcall("svn diff -c %d %s" % (revnum, rootrepo), timeout=3)
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
    
    # Update all externals recursively.
    for ex in getExternals(revnum):
        print "Extern:", ex
        if ex.broken:
            removeExternal(ex)
        else:
            if ex.isdirectory:
                if not os.path.exists(ex.object):
                    os.makedirs(ex.object)
                if os.path.exists( os.path.join(ex.object, '.svn') ):
                    retval = call("svn switch --ignore-externals --ignore-ancestry -r %d %s@%d %s" % (ex.rev, ex.url, ex.pegrev, ex.object))
                else:
                    retval = call("svn co --ignore-externals -r %d %s@%d %s" % (ex.rev, ex.url, ex.pegrev, ex.object))
                if retval != 0:
                    raise RuntimeError("svn error") # TODO: let's report this error explicitly.
                os.chdir(ex.object)
                updateExternalsTo(revnum)
                os.chdir(cwd)
            else:
                if os.path.exists(ex.object) and not os.path.isdir(ex.object):
                    os.remove(ex.object)
                if call("svn export -r %d %s@%d %s" % (ex.rev, ex.url, ex.pegrev, ex.object))!= 0:
                    raise RuntimeError("svn error") # TODO: let's report this error explicitly.

#
# Helper Functions
#

def deleteAllSvnContentInCwd():
    for item in os.listdir(os.getcwd()):
        if not item in ['.git']:
            call("rm -fr %s" % item)
            
#============================================================#

#
# Parse input parameters
#      
            
rootrepo, repo, remoterepos, targetdir, usersfile, checkancestry = parseOptions()
userLookup = getUserLookup(usersfile)

#
# Debug: check ancestry
#


if checkancestry:
    startrevnum = 0
    lastrev = getLastRevision(repo)
    revnumbers = range(startrevnum, lastrev.number + 1)
    print "Ancestry for %s from %d to %d" % (repo, lastrev.number, startrevnum)
    
    prevRevUrl = ""
    prevPegUrl = ""
    for revnum in revnumbers:
        printInfo = False
        # Rev only
        try:
            url = getUrlForRepoAtRevision(repo, rev=revnum)
        except CalledProcessError as e:
            if e.stderr.find("Unable to find repository location") != -1\
               or e.stderr.find("non-existent in revision") != -1:
                url = "Not present in repo"
            else:
                raise
        if url != prevRevUrl:
            print "####\t%d r:\t%s" % (revnum, url)
            prevRevUrl = url
            printInfo = True
            
        # Peg only
        try:
            url = getUrlForRepoAtRevision(repo, peg=revnum)
        except CalledProcessError as e:
            if e.stderr.find("Unable to find repository location") != -1\
               or e.stderr.find("non-existent in revision") != -1:
                url = "Not present in repo"
            else:
                raise
        if url != prevPegUrl:
            print "####\t%d p:\t%s" % (revnum, url)
            prevPegUrl = url
            printInfo = True
        
        # Print info for relevant changes
        if printInfo:
            call("svn log -r %d %s" % (revnum, rootrepo), printcommand=False)
    exit()
    

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


for revnum in revnumbers:
    print "\n-------- Replaying revision %d --------\n" % revnum
    rev = getRevision(revnum)
    print rev
    
    ignoreThisChange = False
    
    # If any externals change, nuke the entire repo and get the externals fresh.
    # This way, we don't have to look into the history to figure out what to delete.
    # Trust me this will be faster.
    if didExternalsChange(revnum):
        print "Externals changed, nuking the entire repo."
        deleteAllSvnContentInCwd()

    # Update project root to revision
    try:
        if os.path.exists('.svn'):
            text, errmsg = readcall("svn switch --ignore-externals --accept theirs-full -r %d %s" % (rev.number, repo), printstdout=True)
        else:
            text, errmsg = readcall('svn co --ignore-externals -r %d %s .' % (rev.number, repo), printstdout=True)
    except CalledProcessError as e:
        if e.stderr.find("Unable to find repository location") != -1:
            print "Operative-revision ancestry has a gap here (probably caused by branching from a past revision.) Ignoring this commit."
            ignoreThisChange = True
        else:
            raise
    
    if not ignoreThisChange:
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

