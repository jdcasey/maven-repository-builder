import json
import logging
import os
import sys

import maven_repo_util


class Configuration:
    """
    Class holding Artifact List Generator configuration. It can be loaded
    from a json configuration file.
    """

    singleVersion = None
    artifactSources = []
    excludedGAVs = []
    excludedRepositories = []
    multiVersionGAs = []
    _configFiles = set()
    allClassifiers = False

    def load(self, opts):
        """
        Load confiugration from command line arguments

        :param opts: options parsed by an OptionParser
        """

        if opts.config is None:
            logging.error('You must specify a config file')
            sys.exit(1)

        self.allClassifiers = opts.allclassifiers

        self.loadFromFile(opts.config)

    def loadFromFile(self, filename):
        self._loadFromFile(filename)
        self._setDefaults()
        self._validate()

    def _setDefaults(self):
        if self.singleVersion is None:
            self.singleVersion = True
        for source in self.artifactSources:
            if source['type'] == 'dependency-list':
                if 'recursive' not in source:
                    source['recursive'] = True
                if 'skip-missing' not in source:
                    source['skip-missing'] = True

    def _validate(self):
        valid = True
        if self.singleVersion is None:
            logging.error("Option single-version not set in configuration file.")
            valid = False
        if not self.artifactSources:
            logging.error("No artifact-sources set in configuration file.")
            valid = False
        if not valid:
            sys.exit(1)

    def _loadFromFile(self, filename, rewrite=True):
        """ Load confiugration from json config file. """
        logging.debug("Loading configuration file %s", filename)
        if filename in self._configFiles:
            raise Exception("Config file '%s' is already included." % filename +
                            " Check your config files for circular inclusions.")
        self._configFiles.add(filename)
        data = json.load(open(filename))

        filePath = os.path.dirname(filename)
        if filePath:
            filePath += '/'

        if 'include-high-priority' in data and data['include-high-priority']:
            inclFile = self._getRelativeFilename(data['include-high-priority'], filePath)
            self._loadFromFile(inclFile, True)

        if (rewrite or self.singleVersion is None) and 'single-version' in data:
            self.singleVersion = maven_repo_util.str2bool(data['single-version'])

        if 'artifact-sources' in data:
            self._loadArtifactSources(data['artifact-sources'], filePath)

        if 'excluded-gav-patterns-ref' in data:
            for filename in data['excluded-gav-patterns-ref']:
                relFilename = self._getRelativeFilename(filename, filePath)
                self.excludedGAVs.extend(self._loadFlatFile(relFilename))

        if 'excluded-repositories' in data:
            self.excludedRepositories.extend(data['excluded-repositories'])

        if 'multi-version-ga-patterns-ref' in data:
            for filename in data['multi-version-ga-patterns-ref']:
                relFilename = self._getRelativeFilename(filename, filePath)
                self.multiVersionGAs.extend(self._loadFlatFile(relFilename))

        if 'multi-version-ga-patterns' in data:
            self.multiVersionGAs.extend(data['multi-version-ga-patterns'])

        if 'include-low-priority' in data and data['include-low-priority']:
            inclFile = self._getRelativeFilename(data['include-low-priority'], filePath)
            self._loadFromFile(inclFile, False)

    def _loadArtifactSources(self, artifactSources, filePath):
        for source in artifactSources:
            if not 'type' in source:
                logging.error("Source doesn't have type.\n %s", str(source))
                sys.exit(1)
            if source['type'] == 'mead-tag':
                source['included-gav-patterns'] = self._loadFlatFileBySourceParameter(source,
                        'included-gav-patterns-ref', filePath)
            elif source['type'] == 'dependency-list':
                if 'recursive' in source:
                    source['recursive'] = maven_repo_util.str2bool(source['recursive'])
                if 'skip-missing' in source:
                    source['skip-missing'] = maven_repo_util.str2bool(source['skip-missing'])
                source['repo-url'] = self._getRepoUrl(source)
                source['top-level-gavs'] = self._loadFlatFileBySourceParameter(source, 'top-level-gavs-ref',
                        filePath)
            elif source['type'] == 'repository':
                source['repo-url'] = self._getRepoUrl(source)
                source['included-gav-patterns'] = self._loadFlatFileBySourceParameter(source,
                        'included-gav-patterns-ref', filePath)
            self.artifactSources.append(source)

    def _loadFlatFileBySourceParameter(self, source, parameter, filePath):
        if parameter in source:
            relFilename = self._getRelativeFilename(source[parameter], filePath)
            return self._loadFlatFile(relFilename)
        else:
            return []

    def _loadFlatFile(self, filename):
        if filename:
            with open(filename, "r") as openedfile:
                lines = openedfile.readlines()
            result = []
            for line in lines:
                resultLine = line.strip()
                if resultLine:
                    result.append(resultLine)
            return result

    def _getRelativeFilename(self, filename, path):
        """Checks, if the given filename has absolute path, and if not, it preppends to it given path."""
        if os.path.isabs(filename):
            return filename
        else:
            return path + filename

    def _getRepoUrl(self, source):
        if not 'repo-url' in source:
            logging.error("Source %s must have specified repo-url.", source['type'])
            sys.exit(1)
        if isinstance(source['repo-url'], basestring):
            return [source['repo-url']]
        else:
            return source['repo-url']
