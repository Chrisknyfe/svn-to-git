#!/bin/sh

# Create a new master 
git branch -m master old-master
git checkout --orphan new-master
git reset --hard
touch .gitignore
git add .gitignore
git commit -m "Creating the interleaved repo (beginning of git_cherry_sort)"

# Bring changes from old master into this one, but sorted and cherry-picked.
git log --oneline --reverse old-master | awk '{ print $1 }' | xargs -L1 git cherry-pick
git filter-branch -f --env-filter 'GIT_COMMITTER_DATE=$GIT_AUTHOR_DATE; export GIT_COMMITTER_DATE'

# Old master, we no longer need you.
git branch -m new-master master
git branch -D old-master
