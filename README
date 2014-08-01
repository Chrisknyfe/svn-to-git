svn-to-git
==========

Tools for exporting an SVN project to GIT

-- Dependencies --

Python 2 (only 2 supported for now)
Subversion 1.5+
Git 1.X+

-- Overview --

convert-to-git.py:
  Converts an SVN repository into a Git project, merging in the history of all externals as if they had been developed inside the parent project itself. If your SVN project has a lot of externals, this script will "flatten" the project for you. 
  
  Example usage:
  
  python convert-to-git.py --root file:///home/chrisknyfe/localsvnrepo --repo /path/to/subproject \
  --users users.txt export_dir
  
  This will export changes from the project at file:///home/chrisknyfe/localsvnrepo/path/to/subproject and commit them to a local git project in export_dir. The history that will be exported from the svn repo follows the history of the object at the path /path/to/subproject at the latest revision. The object may have been moved many times, but this script will still get the history of the object as it was at those other locations. 
  
git-filter-prefix.sh:
  Rewrites the history of the current git project as if it had been developed in a subdirectory.
  
  Example usage:
  bash git-filter-prefix.sh prefix/path
  
  If your git repository has a README, that file will now exist at prefix/path/README for the entire history of the project.
  
git-cherry-sort.sh:
  Sort the commits in the master branch of the current git project by date, flattening their history into one linear history. 
  
  Usage:
  bash git-cherry-sort.sh
  
  Useful if you created a git project by pulling history from many other git projects. All the history is there, but if you try to checkout a commit that originated from one of the git projects you pulled, you won't be able to see the content from any of the other git projects.
  
  I'm using git-cherry-sort.sh and git-filter-prefix.sh to take many separate libraries in separate SVN projects and put them together in one git project as subdirectories, as if they had all been developed together. You can see an example of this in create-libraries.py

-- Known Issues --

* Relative externals won't be parsed properly (yet)
* convert-to-git.py does not support externs that reference SVN repos on other hosts (yet)
* For performance and network bandwidth reasons, you should get a local mirror of your SVN repository and export from that instead of from the remote repository over the network. See "svnclone.sh" for an example of how to clone an svn repository locally.
* For performance reasons, you should run this script on a filesystem that supports timestamp granularity of less than 1 second. When svn performs an "svn checkout" or "svn export", apparently it waits for the system to generate a unique timestamp. I recommend an ext4 filesystem, the default for newer linux distributions.

-- References --

externals definition: http://svnbook.red-bean.com/en/1.7/svn.advanced.externals.html
users.txt format: http://git-scm.com/book/en/Git-and-Other-Systems-Migrating-to-Git
git-filter-branch subdirectory rewrite: http://git-scm.com/docs/git-filter-branch
  The example on this page for moving a whole tree into a subdirectory didn't work on my system because some versions of bash don't seem to support inline bash variable assignment.
svn local mirror: http://cournape.wordpress.com/2007/12/18/making-a-local-mirror-of-a-subversion-repository-using-svnsync/

See LICENSE for more information on copying and redistributing these tools.
