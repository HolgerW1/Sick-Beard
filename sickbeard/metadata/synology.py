# Author: Holger Wiedemann <holger.wiedemann.it@gmail.com>
# Created for Synology NAS, based on mediabrowser
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import os
import re

import sickbeard

import generic

from sickbeard import logger, exceptions, helpers
from sickbeard import encodingKludge as ek
from lib.tvdb_api import tvdb_api, tvdb_exceptions
from sickbeard.exceptions import ex

import json

class SynologyMetadata(generic.GenericMetadata):
    """
    Metadata generation class for Synology VideoStation.
    
    The following file structure is used:
    
    show_root/Season 01/show - 1x01 - episode.mkv  (* example of existing ep of course)
    show_root/Season 01/@eaDir/show - 1x01 - episode.mkv/SYNOVIDEO_VIDEO_SCREENSHOT.jpg  (episode thumb)
    show_root/Season 01/@eaDir/show - 1x01 - episode.mkv/SYNOVIDEO_TV_EPISODE  (episode metadata)
    """
    
    def __init__(self,
                 show_metadata=False,
                 episode_metadata=False,
                 fanart=False,
                 poster=False,
                 banner=False,
                 episode_thumbnails=False,
                 season_posters=False,
                 season_banners=False,
                 season_all_poster=False,
                 season_all_banner=False):

        generic.GenericMetadata.__init__(self,
                                         show_metadata,
                                         episode_metadata,
                                         fanart,
                                         poster,
                                         banner,
                                         episode_thumbnails,
                                         season_posters,
                                         season_banners,
                                         season_all_poster,
                                         season_all_banner)
        
        self.name = 'Synology'
        
        self._show_file_name = 'series.xml'
        
        # web-ui metadata template
        self.eg_show_metadata = "<i>not supported</i>"
        self.eg_episode_metadata = "@eaDir\\<i>filename</i>\\SYNOVIDEO_TV_EPISODE"
        self.eg_fanart = "<i>not supported</i>"
        self.eg_poster = "folder.jpg"
        self.eg_banner = "<i>not supported</i>"
        self.eg_episode_thumbnails = "@eaDir\\<i>filename</i>\\SYNOVIDEO_VIDEO_SCREENSHOT.jpg"
        self.eg_season_posters = "<i>not supported</i>"
        self.eg_season_banners = "<i>not supported</i>"
        self.eg_season_all_poster = "<i>not supported</i>"
        self.eg_season_all_banner = "<i>not supported</i>"
    
    # Override and implement features for Synology VideoStation
    def get_episode_thumb_path(self, ep_obj):
        """
        Returns the path where the episode thumbnail should be stored. Defaults to
        the same path as the episode file but with a .metathumb extension.
        
        ep_obj: a TVEpisode instance for which to create the thumbnail
        """
        if ek.ek(os.path.isfile, ep_obj.location):
            tbn_filename = 'SYNOVIDEO_VIDEO_SCREENSHOT.jpg'
            tbn_dir_name = ek.ek(os.path.join, ek.ek(os.path.dirname, ep_obj.location), '@eaDir', ek.ek(os.path.basename, ep_obj.location))
            tbn_filepath = ek.ek(os.path.join, tbn_dir_name, tbn_filename)            
        else:
            return None
        
        return tbn_filepath

    # Override and implement features for Synology
    def get_episode_file_path(self, ep_obj):
        """
        Returns the full path for the Synology episode metadata
        show dir/@eaDir/episode/SYNOVIDEO_TV_EPISODE
        
        ep_obj: a TVEpisode object to get the path for
        """
        if ek.ek(os.path.isfile, ep_obj.location):
            metadata_file_name = 'SYNOVIDEO_TV_EPISODE'
            metadata_dir_name = ek.ek(os.path.join, ek.ek(os.path.dirname, ep_obj.location), '@eaDir', ek.ek(os.path.basename, ep_obj.location))
            metadata_file_path = ek.ek(os.path.join, metadata_dir_name, metadata_file_name)
        else:
            logger.log(u"Episode location doesn't exist: " + str(ep_obj.location), logger.DEBUG)
            return ''
        
        return metadata_file_path

    def _ep_data(self, ep_obj):
        """
        Creates a JSON structure for a Synology style metadata file
        and returns the resulting data object.
        
        ep_obj: a TVShow instance to create the JSON for
        """
        
        data = {};
        
        eps_to_write = [ep_obj] + ep_obj.relatedEps
        
        tvdb_lang = ep_obj.show.lang

        try:
            # There's gotta be a better way of doing this but we don't wanna
            # change the language value elsewhere
            ltvdb_api_parms = sickbeard.TVDB_API_PARMS.copy()

            if tvdb_lang and not tvdb_lang == 'en':
                ltvdb_api_parms['language'] = tvdb_lang

            t = tvdb_api.Tvdb(actors=True, **ltvdb_api_parms)
            myShow = t[ep_obj.show.tvdbid]
        except tvdb_exceptions.tvdb_shownotfound, e:
            raise exceptions.ShowNotFoundException(str(e))
        except tvdb_exceptions.tvdb_error, e:
            logger.log("Unable to connect to TVDB while creating meta files - skipping - " + str(e), logger.ERROR)
            return False
        
        for curEpToWrite in eps_to_write:
        
            try:
                myEp = myShow[curEpToWrite.season][curEpToWrite.episode]
            except (tvdb_exceptions.tvdb_episodenotfound, tvdb_exceptions.tvdb_seasonnotfound):
                logger.log("Unable to find episode " + str(curEpToWrite.season) + "x" + str(curEpToWrite.episode) + " on tvdb... has it been removed? Should I delete from db?")
                return None
            
            if myEp["firstaired"] == None and ep_obj.season == 0:
                myEp["firstaired"] = str(datetime.date.fromordinal(1))
            
            if myEp["episodename"] == None or myEp["firstaired"] == None:
                return None
                
            if myShow["seriesname"] != None: 
                data['title'] = myShow["seriesname"]
            
            data['tagline'] = curEpToWrite.name
            data['season'] = str(curEpToWrite.season)
            data['episode'] = str(curEpToWrite.episode)
            
            if curEpToWrite.description != None:
            	data['summary'] = curEpToWrite.description
            
            if curEpToWrite.airdate != datetime.date.fromordinal(1):
                data['original_available'] = str(curEpToWrite.airdate)
            
            if myEp['writer'] != None:
            	data['writer'] = myEp['writer'].split('|')
            
            if myEp['director'] != None:
            	data['director'] = [ myEp['director'] ]

            if myShow['actors'] != None:
            	data['actor'] = myShow['actors'].split('|')
            	
            if myShow['genre'] != None:
                data['genre'] = myShow['genre'].split('|')
            
        return data

    def write_ep_file(self, ep_obj):
        """
        Generates and writes ep_obj's metadata under the given path with the
        given filename root. Uses the episode's name with the extension in
        _ep_nfo_extension.
        
        ep_obj: TVEpisode object for which to create the metadata
        
        file_name_path: The file name to use for this metadata. Note that the extension
                will be automatically added based on _ep_nfo_extension. This should
                include an absolute path.
        
        Note that this method expects that _ep_data will return an ElementTree
        object. If your _ep_data returns data in another format you'll need to
        override this method.
        """
        
        data = self._ep_data(ep_obj)
        
        if not data:
            return False
        
        nfo_file_path = self.get_episode_file_path(ep_obj)
        nfo_file_dir = ek.ek(os.path.dirname, nfo_file_path)
        meta_file_dir = ek.ek(os.path.dirname, nfo_file_dir)
        
        try:
            if not ek.ek(os.path.isdir, meta_file_dir):
                logger.log("Metadata dir didn't exist, creating it at " + meta_file_dir, logger.DEBUG)
                ek.ek(os.makedirs, meta_file_dir)
                helpers.chmodAsParent(meta_file_dir)
            
            if not ek.ek(os.path.isdir, nfo_file_dir):
                logger.log("Metadata dir didn't exist, creating it at " + nfo_file_dir, logger.DEBUG)
                ek.ek(os.makedirs, nfo_file_dir)
                helpers.chmodAsParent(nfo_file_dir)
            
            logger.log(u"Writing episode metadata file to " + nfo_file_path)
            
            nfo_file = ek.ek(open, nfo_file_path, 'w')
            
            json.dump(data, nfo_file)
            
            nfo_file.close()
            helpers.chmodAsParent(nfo_file_path)
        except IOError, e:
            logger.log(u"Unable to write file to " + nfo_file_path + " - are you sure the folder is writable? " + ex(e), logger.ERROR)
            return False
        
        return True

    # Override with empty methods for unsupported features
    def retrieveShowMetadata(self, folder):
        # no show metadata generated, we abort this lookup function
        return (None, None)

    def create_show_metadata(self, show_obj):
        pass

    def get_show_file_path(self, show_obj):
        pass

    def get_season_poster_path(self, show_obj, season):
        pass

    def create_fanart(self, show_obj):
        pass

    def create_banner(self, show_obj):
        pass

    def create_season_banners(self, show_obj):
        pass

    def create_season_all_poster(self, show_obj):
        pass

    def create_season_all_banner(self, show_obj):
        pass

# present a standard "interface"
metadata_class = SynologyMetadata
