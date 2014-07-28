#!/bin/sh

PREFIX=$1
echo Filtering `pwd` as if it were developed inside \"$PREFIX\"

#git filter-branch -f --tree-filter '
#TEMP=iCouldntGetTheOfficialScriptToWork
#if [[ ! -e '"$PREFIX"' ]]; then
#	mkdir -p $TEMP
#    git ls-tree --name-only $GIT_COMMIT | xargs -I files mv files $TEMP
#    mkdir -p '"$PREFIX"'
#    mv $TEMP/* '"$PREFIX"'/
#fi'

git filter-branch -f --index-filter \
	'git ls-files -s | sed "s-	\"*-&'"$PREFIX"'/-" > .gitlsfilesprefix
	GIT_INDEX_FILE_OLD=$GIT_INDEX_FILE
	GIT_INDEX_FILE=$GIT_INDEX_FILE.new
	git update-index --index-info < .gitlsfilesprefix
	GIT_INDEX_FILE=$GIT_INDEX_FILE_OLD
	if [[ -e "$GIT_INDEX_FILE.new" ]]; then
		mv "$GIT_INDEX_FILE.new" "$GIT_INDEX_FILE"
	fi' HEAD
