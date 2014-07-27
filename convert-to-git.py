#!/usr/bin/env python

import sys, os, shutil, subprocess, re
from collections import namedtuple

# Input parameters
# TODO: make these command-line parameters.
rootrepo = "file:///Users/zbernal/proj/migration/localsvn"
repo = rootrepo + "/trunk/src/sensory/Tools/BCS/dev/BandageCommServer"

remoterepos = ["https://pl3.projectlocker.com/Vigilo/orion/svn", "https://equity3.projectlocker.com/Vigilo/orion/svn"]

targetdir = sys.argv[1] if len(sys.argv) > 1 else "export"

userLookup = {
"bkhor@vitalconnect.com": "Boon Khor <bkhor@vitalconnect.com>",
"bkinman@vigilonetworks.com": "Brandon Kinman <bkinman@vigilonetworks.com>",
"bwang@vigilonetworks.com": "Bruce Wang <bwang@vigilonetworks.com>",
"cdohnal@vitalconnect.com": "Chris Dohnal <cdohnal@vitalconnect.com>",
"nferdosi@vigilonetworks.com": "Nersi Federosi <nferdosi@vigilonetworks.com>",
"rlarsen@vigilonetworks.com": "Russell Larsen <rlarsen@vigilonetworks.com>",
"tframhein@vitalconnect.com": "Teddy Framhein <tframhein@vitalconnect.com>",
"twicken@vigilonetworks.com": "Tyler Wickenhauser <twicken@vigilonetworks.com>",
"twicken@vitalconnect.com": "Tyler Wickenhauser <twicken@vitalconnect.com>",
"zbernal@vitalconnect.com": "Zach Bernal <zbernal@vitalconnect.com>",
"jalisago@vigilonetworks.com": "Jim Alisago <jalisago@vigilonetworks.com>",
"spetersen@vigilonetworks.com": "Steve Petersen <spetersen@vigilonetworks.com>",
"rnarasimhan@vigilonetworks.com": "Ravi Narasimhan <rnarasimhan@vigilonetworks.com>",
"bt@vigilonetworks.com": "Build Test <bt@vigilonetworks.com>",
"paulkang@viteme.net": "Paul Kang <paulkang@viteme.net>",
"bjorn@vigilonetworks.com": "Bjorn Jorde <bjorn@vigilonetworks.com>",
"sseike@vigilonetworks.com": "Steve Seike <sseike@vigilonetworks.com>",
"yyang@vigilonetworks.com": "Yun Yang <yyang@vigilonetworks.com>",
"kmallela@vigilonetworks.com": "Kesava Mallela <kmallela@vigilonetworks.com>",
"tnguyen@vitalconnect.com": "Tam Nyugen <tnguyen@vitalconnect.com>",
"jdring@vitalconnect.com": "John Dring <jdring@vitalconnect.com>"
}

#
# Shell command wrappers
#

def call(cmd):
	print cmd
	return subprocess.call(cmd, shell=True)
def readcall(cmd):
	print cmd
	return subprocess.check_output(cmd, shell=True)

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

def getUrl(revnum):
	text = readcall("svn info -r %d" % (revnum))
	text = text.splitlines()
	for line in text:
		match = re.search(r'^URL: (.*)$', line)
		if match:
			return match.groups()[0]

def getNodeKindForUrl(url, revnum):
	text = readcall("svn info -r %d %s" % (revnum, url))
	text = text.splitlines()
	for line in text:
		match = re.search(r'^Node Kind: (.*)$', line)
		if match:
			return match.groups()[0]

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

Extern = namedtuple("Extern", ["object", "url", "isdirectory"])

def getExternals(revnum):
	text = readcall("svn propget svn:externals -r %d -R" % (revnum))
	text = text.splitlines()

	currentParentDir = None
	for line in text:
		tokens = line.split()
		if len(tokens) == 2 or len(tokens) == 4:
			if tokens[1] == "-" and len(tokens) == 4:
				currentParentDir = tokens[0]
				if re.search(r'^.*://', currentParentDir):
					# Great, they gave us a URL when we needed a relative path. Let's remake the relative path.
					url = getUrl(revnum)
					currentParentDir = currentParentDir.replace(url, "")
					if currentParentDir[0] == '/':
						currentParentDir = currentParentDir[1:]

				#print "currentParentDir:", currentParentDir
				tokens = tokens[2:]

			if tokens[1] != "-": # I guess when we remove an extern it shows up as "dir -"
				if re.search(r'^https*://', tokens[0]): # TODO: just search for '^*://', could be any protocol.
					childObject = currentParentDir + "/" + tokens[1]
					externUrl = tokens[0]
				elif re.search(r'^https*://', tokens[1]):
					childObject = currentParentDir + "/" + tokens[0]
					externUrl = tokens[1]
				else:
					print "Here's the entire text:"
					print text
					print "Here's the tokens:", tokens
					raise RuntimeError("Where's the URL?: %s" % line)
				# Doctor the URL if we're using a local mirror of a remote repo
				if remoterepos:
					for remoterepo in remoterepos:
						externUrl = externUrl.replace(remoterepo, rootrepo)

				nodekind = getNodeKindForUrl(externUrl, revnum)
				print "Node Kind for %s@%d is %s" % (externUrl, revnum, nodekind)
				#print "childDir:", childDir
				#print "externUrl:", externUrl
				yield Extern(object=childObject, url=externUrl, isdirectory=(nodekind == "directory"))
		elif len(tokens) != 0:
			print "Here's the entire text:"
			print text
			raise RuntimeError("line with odd number of tokens: %s" % line)

def didExternalsChange(revnum):
	text = readcall("svn diff -c %d" % (revnum))
	if text.find("Modified: svn:externals") != -1:
		return True
	else:
		return False

def updateExternalsTo(revnum):
	cwd = os.getcwd()

	# Make sure removed externals don't get kept.
	if didExternalsChange(revnum):
		print "Externals changed, clearing externals."
		for ex in getExternals(revnum-1):
			if ex.isdirectory:
				shutil.rmtree(ex.object)
			else:
				os.remove(ex.object)

	# Update all externals recursively.
	for ex in getExternals(revnum):
		print "Extern:", ex

		# Make sure the extern's url contains a revision number, if not provided.
		exrevnum = revnum
		exurl = ex.url
		match = re.search(r'(.*)@(.*)', exurl)
		if match:
			exurl = match.groups()[0]
			exrevnum = int(match.groups()[1])
			print "Externs %s specified revision to %d" % (exurl, exrevnum)

		if ex.isdirectory:
			if not os.path.exists(ex.object):
				os.makedirs(ex.object)
			if os.path.exists( os.path.join(ex.object, '.svn') ):
				retval = call("svn switch --ignore-externals -r %d %s@%d %s" % (exrevnum, exurl, exrevnum, ex.object))
			else:
				retval = call("svn co --ignore-externals -r %d %s@%d %s" % (exrevnum, exurl, exrevnum, ex.object))
			if retval != 0:
				raise RuntimeError("svn error")
			os.chdir(ex.object)
			updateExternalsTo(revnum)
			os.chdir(cwd)
		else:
			if os.path.exists(ex.object):
				os.remove(ex.object)
			if call("svn export -r %d %s@%d %s" % (exrevnum, exurl, exrevnum, ex.object))!= 0:
				raise RuntimeError("svn error")

#
# Helper Functions
#

def deleteAllContentInCwd():
	for item in os.listdir(os.getcwd()):
		if not item in ['.git', '.svn']:
			call("rm -fr %s" % item)

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
# revision 3385, BandageCommServer was brought back.

# revision 9000, sensor_stream has a file extern "vc_queue.h" # handled

#testpoint = 9000
#revnumbers = xrange(testpoint, testpoint+5)

for revnum in revnumbers:
	print "\n-------- Replaying revision %d --------\n" % revnum
	rev = getRevision(rootrepo, revnum)

	# Update project root to revision
	if os.path.exists('.svn'):
		retval = call("svn switch --ignore-externals -r %d %s@%d" % (rev.number, repo, rev.number))
	else:
		retval = call('svn co --ignore-externals -r %d %s@%d .' % (rev.number, repo, rev.number))
	if retval != 0:
		if isThisPathDeleted(repo, rev.number):
			print "Oh, this path was deleted! Someone forgot how to merge... Remove everything for now."
			deleteAllContentInCwd()
		else:
			raise RuntimeError("svn error")
	else:
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

