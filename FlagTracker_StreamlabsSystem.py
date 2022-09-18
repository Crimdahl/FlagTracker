# -*- coding: utf-8 -*-
import sys
import clr
import codecs
import io
import json
import os
import threading
import traceback
import logging
from time import strftime
from datetime import datetime, timedelta
from time import sleep


# Try/Except here to avoid exceptions when __main__ code at the bottom
try:
    clr.AddReference("IronPython.Modules.dll")
    clr.AddReferenceToFileAndPath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                               "References",
                                               "TwitchLib.PubSub.dll"))
    from TwitchLib.PubSub import TwitchPubSub
except:
    raise RuntimeError("Failed to import TwitchPubSub.")

#   Script Information <Required>
ScriptName = "FlagTracker"
Website = "https://www.twitch.tv/Crimdahl"
Description = "Tracks User Flag Redemptions by writing to json file."
Creator = "Crimdahl"
Version = "v2.1.2"

#   Define Global Variables <Required>
SCRIPT_PATH = os.path.dirname(__file__)
GOOGLE_UPDATER_PATH = os.path.join(SCRIPT_PATH, "GoogleSheetsUpdater.exe")
SETTINGS_PATH = os.path.join(SCRIPT_PATH, "settings.json")
README_PATH = os.path.join(SCRIPT_PATH, "Readme.md")
LOG_PATH = os.path.join(SCRIPT_PATH, "flagtrackerlog-" +
                        strftime("%Y%m%d-%H%M%S") + ".txt")
REDEMPTIONS_PATH = os.path.join(SCRIPT_PATH, "redemptions.json")
TOKEN_PATH = os.path.join(SCRIPT_PATH, "token.json")

script_settings = None
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(funcName)s |  %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)
log_file = None
redemptions = []

redemption_receiver = None
redemption_thread_queue = []
redemption_thread = None
is_reconnect = False
next_reconnect_attempt = datetime.now() + timedelta(seconds=30)
next_token_validity_check = datetime.now() + timedelta(seconds=30)
validity_warning_issued = False

script_uptime = None
retry_count = 0


class TestRedemptionEvent(object):
    def __init__(self, **kwargs):
        self.Username = kwargs["RewardTitle"] if "RewardTitle" in kwargs else "Unknown"
        self.Game = kwargs["Status"] if "Status" in kwargs else "Unknown"
        self.Message = kwargs["DisplayName"] if "DisplayName" in kwargs else "Unknown"
        self.Message = kwargs["Message"] if "Message" in kwargs else "Unknown"
        pass


# Define Redemptions
class Redemption(object):
    def __init__(self, **kwargs):
        self.Username = kwargs["Username"] if "Username" in kwargs else "Unknown"
        self.Game = kwargs["Game"] if "Game" in kwargs else "Unknown"
        self.Message = kwargs["Message"] if "Message" in kwargs else "Unknown"

    def to_json(self):
        return {"Username": self.Username, "Game": self.Game, "Message": self.Message}

    def set_game(self, value):
        self.Game = value

    def set_username(self, value):
        self.Username = value

    def set_message(self, value):
        self.Message = value

    def __str__(self):
        return "Username: " + str(self.Username) + ", Game: " + str(self.Game) + ", Message: " + str(self.Message)


# Define Settings. If there is no settings file created, then use default values in else statement.
class Settings(object):
    def __init__(self, settings_path=None):
        if settings_path and os.path.isfile(settings_path):
            with codecs.open(settings_path, encoding="utf-8-sig", mode="r") as f:
                self.__dict__ = json.load(f, encoding="utf-8")
        else:
            # Permission Settings
            self.HelpDisplayPermissions = "Everyone"
            self.QueueDisplayPermissions = "Everyone"
            self.QueueFindPermissions = "Everyone"
            self.QueueRemovePermissions = "Moderator"
            self.QueueAddPermissions = "Moderator"
            self.QueueEditPermissions = "Moderator"
            self.GoogleUpdaterPermissions = "Moderator"
            self.VersionCheckPermissions = "Moderator"
            self.UptimeDisplayPermissions = "Moderator"
            self.ReconnectPermissions = "Moderator"
            self.TokenDisplayPermissions = "Moderator"

            # Output Settings
            self.RetainLogFiles = False
            self.EnableResponses = True
            self.DisplayMessageOnGameUnknown = False
            self.RunCommandsOnlyWhenLive = True
            self.CommandName = "queue"
            self.DisplayLimit = "10"

            # Twitch Settings
            self.TwitchOAuthToken = ""
            self.TwitchRewardNames = ""
            self.ReconnectionAttempts = 5
            self.TokenValidityCheckInterval = 10

            # Google Sheets Settings
            self.EnableGoogleSheets = False
            self.SpreadsheetID = ""
            self.Sheet = ""

    def Reload(self, data):
        self.__dict__ = json.loads(data, encoding="utf-8")
        return

    def Save(self, settings_path):
        try:
            with codecs.open(settings_path, encoding="utf-8-sig", mode="w+") as f:
                json.dump(self.__dict__, f, encoding="utf-8")
        except Exception as e:
            logging.critical(traceback.print_exc())
            raise e
        return


#   Process messages <Required>
def Execute(data):
    user_id = get_user_id(data.RawData)

    # Check if the streamer is live. Still run commands if the script is set to run while offline
    if ((Parent.IsLive() or not script_settings.RunCommandsOnlyWhenLive) and
            str(data.Message).startswith("!" + script_settings.CommandName)):
        # Check if the message begins with "!" and the command name AND the user has permissions to run the command
        if data.GetParamCount() == 1:
            if Parent.HasPermission(data.User, script_settings.QueueDisplayPermissions, "") or user_id == "216768170":
                logging.debug("No-argument call received.")
                # If the user is using Google Sheets, post a link to the Google Sheet in chat
                if script_settings.EnableGoogleSheets and script_settings.SpreadsheetID != "":
                    logging.debug("Displaying Google Sheets link in chat: " +
                                  "https://docs.google.com/spreadsheets/d/" + script_settings.SpreadsheetID)
                    post("Flagtracker: https://docs.google.com/spreadsheets/d/" + script_settings.SpreadsheetID)
                    return
                # If the user is not using Google Sheets, read lines from the json file in the script directory
                else:
                    logging.debug("Displaying " + str(script_settings.DisplayLimit) + " redemptions in chat.")
                    if len(redemptions) > 0:
                        # An index is displayed with each line. The index can be referenced with other commands.
                        index = 1
                        for redemption in redemptions:
                            if script_settings.DisplayMessageOnGameUnknown \
                                    and str(redemption.Game).lower().strip() == "unknown":
                                post(str(index) + ") " + redemption.Username + " - " + redemption.Message)
                            else:
                                post(str(index) + ") " + redemption.Username + " - " + redemption.Game)
                            index = index + 1
                            if index > script_settings.DisplayLimit:
                                break
                        return
                    else:
                        post("Flagtracker: The community queue is empty!")
            else:
                post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
        else:
            subcommand = data.GetParam(1)
            if subcommand == "find":
                if (Parent.HasPermission(data.User, script_settings.QueueFindPermissions, "") or
                                         user_id == "216768170"):
                    if data.GetParamCount() < 4:
                        if data.GetParamCount() == 2:
                            # No username supplied. Search for redemptions by the user that posted the command.
                            search_username = data.User
                        else:
                            # Username supplied. Search for redemptions by the supplied username
                            search_username = data.GetParam(2)
                        logging.debug("Searching for user " + str(search_username) + " in the queue.")
                        index = 1
                        found = False
                        for redemption in redemptions:
                            if str(redemption.Username).lower() == str(search_username).lower():
                                if script_settings.DisplayMessageOnGameUnknown and \
                                        str(redemption.Game).lower().strip() == "unknown":
                                    post(str(index) + ") " + str(redemption))
                                else:
                                    post(str(index) + ") " + str(redemption))
                                found = True
                            index = index + 1
                        if not found:
                            post("Flagtracker: No redemptions were found for the username " + str(search_username) + ".")
                        return
                    else:
                        logging.error("Too many parameters supplied with Find argument: " +
                                      str(data.Message))
                        if script_settings.EnableResponses:
                            post("Usage: !" + script_settings.CommandName + " find {Optional Username}")
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "remove":
                if (Parent.HasPermission(data.User, script_settings.QueueRemovePermissions, "") or
                                         user_id == "216768170"):
                    logging.debug("Remove argument received.")
                    # Check if the supplied information has three or more parameters:
                    #   !command, remove, and one or more indices
                    if data.GetParamCount() >= 3:
                        logging.debug("Removing redemption(s)")
                        data_string = str(data.Message)
                        # Separate the indices from the rest of the message and split them by comma delimiter
                        data_array = data_string[data_string.index("remove") +
                                                 len("remove"):].replace(" ", "").split(",")
                        # It is necessary to remove them from lowest index to highest index, so sort the indices first
                        # Should I just remove from highest to lowest?
                        data_array.sort()
                        logging.debug("Removing the following from Redemptions: " + str(data_array))
                        # Keep track of the number of indices removed because we have to subtract that
                        # number from the supplied indices
                        removed_count = 1
                        try:
                            for num in data_array:
                                # The indices in the redemptions are 0-based,
                                # so we can immediately subtract 1 from any user-supplied indices
                                redemptions.pop(int(num) - removed_count)
                                removed_count = removed_count + 1
                            save_redemptions()
                            logging.debug("Successfully removed " + str(removed_count - 1) + " redemption(s).")
                            post("Flagtracker: Redemption(s) successfully removed.")
                        except (ValueError, IndexError) as e:
                            # Log an error if the index is either a non-integer or is outside of the
                            #   range of the redemptions
                            if isinstance(e, IndexError):
                                logging.error(traceback.format_exc())
                                post("Flagtracker: Supplied index was out of range. The valid range is 1-" +
                                     str(len(redemptions)) + ".")
                            else:
                                # Unanticipated error
                                logging.critical(traceback.format_exc())
                    else:
                        # If the supplied command is just "!<command name> remove" and chat responses are enabled,
                        # display the command usage text in chat.
                        logging.error("Too few parameters provided to Remove argument: " + str(data.Message))
                        if script_settings.EnableResponses:
                            post("Usage: !" + script_settings.CommandName + " remove {index}, {index}")
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "add":
                if Parent.HasPermission(data.User, script_settings.QueueAddPermissions, "") or user_id == "216768170":
                    logging.debug("Add argument received.")
                    # Check if the supplied information has three or more parameters:
                    # !command, add, and one or more sets of information
                    if data.GetParamCount() >= 3:
                        data_string = str(data.Message)
                        # Separate the information sets from the rest of the message and split them by pipe delimiter
                        data_array = data_string[data_string.index("add") + len("add"):].split("|")
                        error_data_array = []
                        logging.debug("Adding redemptions: " + str(data_array))
                        redemptions_added = 0
                        for info in data_array:
                            # Create a redemption object with the Username, Message, and Game
                            try:
                                # Username is mandatory
                                new_user = get_attribute("Username", info)
                                # Message is optional
                                new_message = "No message."
                                try:
                                    new_message = get_attribute("Message", info)
                                except (AttributeError, ValueError):
                                    pass
                                # Game is optional
                                new_game = "Unknown"
                                try:
                                    new_game = get_attribute("Game", info)
                                except (AttributeError, ValueError):
                                    if not new_message == "No message.":
                                        new_game = detect_game("", new_message)
                                    pass
                                new_redemption = Redemption(Username=new_user, Message=new_message, Game=new_game)
                                if "index:" in info:
                                    insertion_index = int(get_attribute("Index", info)) - 1
                                    redemptions.insert(insertion_index, new_redemption)
                                    logging.debug("Redemption inserted at index " + str(insertion_index) + ": " +
                                                  str(new_redemption))
                                    redemptions_added = redemptions_added + 1
                                else:
                                    redemptions.append(new_redemption)
                                    logging.debug("Redemption appended: " + str(new_redemption))
                                    redemptions_added = redemptions_added + 1
                            except (AttributeError, ValueError):
                                error_data_array.append(info)
                                logging.critical(traceback.format_exc())
                                continue
                        # Save the new redemptions. This method also saves to Google Sheets if enabled,
                        # so no additional logic is required to add entries to Google Sheets.
                        if redemptions_added > 0:
                            save_redemptions()
                            if redemptions_added == len(data_array):
                                logging.debug(str(redemptions_added) +
                                              " redemptions were successfully added to the queue.")
                            else:
                                post("Flagtracker: Successfully added " + str(redemptions_added) +
                                     " redemption(s) to the queue, but failed to add " +
                                     str(len(data_array) - redemptions_added) + ". Please see logs for error details.")
                                if error_data_array:
                                    logging.error(str(redemptions_added) +
                                                  " redemptions were successfully added to the queue out of " +
                                                  str(len(data_array)) +
                                                  " attempted. The following redemptions encountered errors: " +
                                                  str(error_data_array))
                                else:
                                    logging.critical(str(redemptions_added) +
                                                     " redemptions were successfully added to the queue out of " +
                                                     str(len(data_array)) +
                                                     " attempted. Failed to document error redemptions.")

                            post("Flagtracker: Successfully added " + str(
                                redemptions_added) + " redemption(s) to the queue.")
                        else:
                            if error_data_array:
                                logging.error("Failed to add " + str(len(data_array)) +
                                              " redemptions to the queue: " + str(error_data_array))
                            else:
                                logging.critical("Failed to add " + str(len(data_array)) +
                                                 " redemptions to the queue. Failed to document error redemptions.")
                            post("Failed to add any redemptions to the queue. "
                                 "Please see the log file for error details.")
                    else:
                        # If the supplied command is just "!<command name> remove" and chat responses are enabled,
                        # display the command usage text in chat.
                        logging.error("Too few parameters provided to Add argument: " + str(data.Message))
                        if script_settings.EnableResponses:
                            post("Usage: !" + script_settings.CommandName +
                                 " add Username:{UserName>}, (Game:{Game}), Message:{Message}")
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "edit":
                if Parent.HasPermission(data.User, script_settings.QueueEditPermissions, "") or user_id == "216768170":
                    logging.debug("Edit argument received.")
                    # This command takes 3 or more parameters: !<command name>, an index,
                    #   and attributes to edit at that index
                    if data.GetParamCount() >= 3:
                        try:
                            changes = False
                            # Get the index and a set of comma-separated attributes from the message
                            index = int(data.GetParam(2))
                            data = str(data.Message)[len("!" + script_settings.CommandName + " edit " +
                                                         str(index)):].split("|")
                            logging.debug("Data supplied to Edit argument: " + str(data))
                            target = redemptions[index - 1]

                            # Attempt to modify each type of attribute. Do nothing if the attribute is not found.
                            # Save only if changes happen.
                            for attribute in data:
                                if "username" in attribute.lower():
                                    try:
                                        target.set_username(get_attribute("Username", attribute))
                                        changes = True
                                    except (AttributeError, ValueError):
                                        logging.critical(traceback.print_exc())
                                if "message" in attribute.lower():
                                    try:
                                        target.set_message(get_attribute("Message", attribute))
                                        changes = True
                                    except (AttributeError, ValueError):
                                        logging.critical(traceback.print_exc())
                                if "game" in attribute.lower():
                                    try:
                                        target.set_game(get_attribute("Game", attribute))
                                        changes = True
                                    except (AttributeError, ValueError):
                                        logging.critical(traceback.print_exc())
                            # Save the modified redemptions. This method also saves to Google Sheets if enabled,
                            # so no additional logic is required to modify entries in Google Sheets.
                            if changes:
                                save_redemptions()
                                logging.debug("Successfully modified redemption.")
                                post("Flagtracker: Redemption successfully modified.")
                            else:
                                logging.error("Failed to the modify redemption at index " + str(index) +
                                              " with message " + str(data))
                        except Exception as e:
                            if isinstance(e, IndexError):
                                logging.error("A bad redemption index was supplied to the Edit argument: " +
                                              traceback.print_exc())
                            elif isinstance(e, ValueError):
                                logging.error("A bad value was supplied to the Edit argument: " + traceback.print_exc())
                            else:
                                logging.critical("The Edit argument generated an unexpected exception: " +
                                                 traceback.print_exc())
                    else:
                        logging.error("Too few parameters provided to Edit argument: " + str(data.Message))
                        if script_settings.EnableResponses:
                            post("Usage: !" + script_settings.CommandName +
                                 " edit <Index> <Username/Game/Message>:<Value>(|<Username/Game/Message>:<Value>|...)")
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "updater":
                if (Parent.HasPermission(data.User, script_settings.GoogleUpdaterPermissions, "") or
                                        user_id == "216768170"):
                    logging.debug("Updater argument received.")
                    if script_settings.EnableGoogleSheets:
                        update_google_sheet()
                        post("Flagtracker: Google Sheets Updater executed.")
                        logging.debug("GoogleSheetsUpdater was successfully started.")
                    else:
                        post("Flagtracker: Google Sheets is disabled.")
                        logging.debug("GoogleSheetsUpdater skipped - Google Sheets is disabled.")
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "version":
                if (Parent.HasPermission(data.User, script_settings.VersionCheckPermissions, "") or
                                         user_id == "216768170"):
                    logging.debug("Version argument received.")
                    global Version
                    try:
                        result = json.loads(
                            Parent.GetRequest("https://api.github.com/repos/Crimdahl/FlagTracker/releases", {}))
                        newest_version = None
                        for index, asset in enumerate(json.loads(result['response'])):
                            try:
                                if not asset['prerelease'] and "beta" not in asset['tag_name']:
                                    newest_version = asset['tag_name']
                                    logging.debug("Non-beta asset found: " + str(newest_version))
                                    break
                                else:
                                    logging.debug("Skipping beta asset: " + str(asset['tag_name']))
                            except KeyError:
                                logging.debug("KeyError for index " + str(index))
                                continue
                        if newest_version:
                            logging.debug(str(Version[1:]) + " > " + str(newest_version[1:]) + "?")
                        if newest_version and (float(newest_version[1:]) > float(Version[1:])):
                            post("Flagtracker is version " + str(Version) + ". The latest version is " + str(
                                newest_version) + ".")
                        else:
                            post("Flagtracker is version " + str(Version) + ". You have the latest version.")
                    except Exception:
                        logging.error(traceback.print_exc())
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "uptime":
                if (Parent.HasPermission(data.User, script_settings.UptimeDisplayPermissions, "")
                                         or user_id == "216768170"):
                    if not script_uptime:
                        post("Flagtracker: The script is not currently connected to the channel.")
                    else:
                        global script_uptime
                        post("Flagtracker: The script has been connected to the channel for " +
                             calculate_time_difference(script_uptime))
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "reconnect":
                if Parent.HasPermission(data.User, script_settings.ReconnectPermissions, "") or user_id == "216768170":
                    global redemption_receiver
                    if redemption_receiver:
                        redemption_receiver.Disconnect()
                    post("Flagtracker: Attempting to connect to Twitch...")
                    Start()
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "token":
                if (Parent.HasPermission(data.User, script_settings.TokenDisplayPermissions, "") or
                                         user_id == "216768170"):
                    try:
                        results = json.loads(Parent.GetRequest("https://id.twitch.tv/oauth2/validate",
                                          {
                                              "Authorization": "OAuth " + script_settings.TwitchOAuthToken
                                          }
                        ))
                        if results["status"] == 200:
                            response = json.loads(results["response"])
                            time_difference = datetime.now() + timedelta(seconds=response["expires_in"])
                            post("Flagtracker: The current token is valid. It will last for " +
                                calculate_time_difference(time_difference))
                        else:
                            global validity_warning_issued
                            post("Flagtracker: The current token is not valid and needs to be refreshed.")
                            validity_warning_issued = True
                    except Exception as ex:
                        logging.error("Error processing the token command: " + str(ex))
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            elif subcommand == "help":
                if (Parent.HasPermission(data.User, script_settings.HelpDisplayPermissions, "") or
                                         user_id == "216768170"):
                    if data.GetParamCount() > 1:
                        help_subcommand = data.GetParam(2)
                        if help_subcommand == "find":
                            post("Flagtracker find subcommand usage: !" + script_settings.CommandName +
                                 " find {username}. Looks through the queue and displays entries from the"
                                 " specified user. Required permission level: '" +
                                 script_settings.QueueFindPermissions + "'.")
                        elif help_subcommand == "add":
                            post("Flagtracker add subcommand usage: !" + script_settings.CommandName +
                                 " add Username:{username}, Game:{game}, Message{redemption message}."
                                 " Adds a new entry to the queue. Required permission level: '" +
                                 script_settings.QueueAddPermissions + "'.")
                        elif help_subcommand == "remove":
                            post("Flagtracker remove subcommand usage: !" + script_settings.CommandName +
                                 " remove {index}. Removes the redemption at the supplied index. Required"
                                 " permission level: '" + script_settings.QueueRemovePermissions + "'.")
                        elif help_subcommand == "edit":
                            post("Flagtracker edit subcommand usage: !" + script_settings.CommandName +
                                 " edit {index} (Username:{username})(,)(Game:{game})(,)(Message:{message})."
                                 " Modifies the username, game, and/or message of the redemption at the supplied"
                                 " index. Required permission level: '" + script_settings.QueueEditPermissions + "'.")
                        elif help_subcommand == "updater":
                            post("Flagtracker updater subcommand usage: !" + script_settings.CommandName +
                                 " updater. Manually updates the Google Sheet, if it is enabled. Required"
                                 " permission level: '" + script_settings.GoogleUpdaterPermissions + "'.")
                        elif help_subcommand == "version":
                            post("Flagtracker version subcommand usage: !" + script_settings.CommandName +
                                 " version. Displays the current version of the script and the latest non-beta"
                                 " script version available on GitHub. Required permission level: '" +
                                 script_settings.VersionCheckPermissions + "'.")
                        elif help_subcommand == "token":
                            post("Flagtracker uptime subcommand usage: !" + script_settings.CommandName +
                                 " token. If the settings have a Twitch oAuth token,"
                                 " validates the token and displays the expiration date: '" +
                                 script_settings.TokenDisplayPermissions + "'.")
                        elif help_subcommand == "uptime":
                            post("Flagtracker uptime subcommand usage: !" + script_settings.CommandName +
                                 " uptime. If the script is connected to Twitch, displays how long the"
                                 " script has been connected. Required permission level: '" +
                                 script_settings.UptimeDisplayPermissions + "'.")
                        else:
                            post("Flagtracker help subcommand usage: !" + script_settings.CommandName +
                                 " help {subcommand}. Current subcommands include find, add, remove, edit, updater,"
                                 " version, uptime, token, and help. Command syntax has variables you supply listed in"
                                 " {brackets} and optional arguments listed in (parenthesis).")
                    else:
                        post("Flagtracker help subcommand usage: !" + script_settings.CommandName +
                             " help {subcommand}. Current subcommands include find, add, remove, edit, updater,"
                             " version, uptime, token, and help. Command syntax has variables you supply listed in"
                             " {brackets} and optional arguments listed in (parenthesis).")
                else:
                    post("Flagtracker: Sorry, " + data.UserName + ", you do not have permission to use that command.")
            else:
                post("Flagtracker: Subcommand '" + subcommand + "' is not recognized. Available subcommands are: " +
                     "find, add, remove, edit, updater, version, uptime, token, and help")


# [Required] Tick method (Gets called during every iteration even when there is no incoming data)
def Tick():
    global next_reconnect_attempt, redemption_thread, script_uptime, retry_count, next_token_validity_check, \
        validity_warning_issued

    # If a thread exists but has completed its task, delete it so we can create a new one for new tasks
    if redemption_thread and not redemption_thread.isAlive():
        redemption_thread = None

    if redemption_thread is None and len(redemption_thread_queue) > 0:
        redemption_thread = redemption_thread_queue.pop(0)
        redemption_thread.start()

    # Event receiver would be None at this point if it got disconnected. Attempt to reconnect if there are remaining
    #   retries and the time period has elapsed.
    if not redemption_receiver and \
            retry_count < script_settings.ReconnectionAttempts and \
            next_reconnect_attempt <= datetime.now() and \
            not validity_warning_issued:
        next_reconnect_attempt = datetime.now() + timedelta(minutes=1)
        logging.debug("Attempting automatic reconnection. Attempt + " + str(retry_count + 1) + " of " +
                      str(script_settings.ReconnectionAttempts) + ".")
        Start()
        if not redemption_receiver:
            logging.debug("Flagtracker: failed to reconnect to Twitch.")
            retry_count += 1
        else:
            retry_count = 0

    if not script_settings.TokenValidityCheckInterval <= 0 and \
            next_token_validity_check <= datetime.now():
        logging.debug("Performing Automatic Token Validity Check.")
        next_token_validity_check = datetime.now() + timedelta(minutes=script_settings.TokenValidityCheckInterval)
        try:
            global validity_warning_issued
            results = json.loads(Parent.GetRequest("https://id.twitch.tv/oauth2/validate",
                                                   {
                                                       "Authorization": "OAuth " + script_settings.TwitchOAuthToken
                                                   }
                                                   ))
            if not results["status"] == 200:
                logging.debug("Token Invalid.")
                if validity_warning_issued:
                    logging.debug("Skipping Token Validity Warning.")
                else:
                    logging.debug("Issuing Token Validity Warning.")
                    post("Flagtracker: The current token has become invalid and needs to be refreshed.")
                    validity_warning_issued = True
                if redemption_thread:
                    # Disconnect the redemption thread since the token is invalid
                    redemption_thread.Disconnect()
                elif script_uptime:
                    # Reset the script uptime
                    script_uptime = None
            else:
                logging.debug("Token Valid.")
                validity_warning_issued = False

        except Exception as ex:
            logging.error("Error attempting to automatically check the validity of the Twitch oAuth token.")
    return


def delete_log_files(create_new_logs=True):
    global LOG_PATH
    for handler in logging.getLogger().handlers:
        handler.close()
        logging.getLogger().removeHandler(handler)
    os.remove(LOG_PATH)

    if create_new_logs:
        # Create new logger
        global LOG_PATH, SCRIPT_PATH
        LOG_PATH = os.path.join(SCRIPT_PATH, "flagtrackerlog-" +
                                strftime("%Y%m%d-%H%M%S") + ".txt")
        logging.basicConfig(
            filename=LOG_PATH,
            level=logging.DEBUG,
            format="%(asctime)s | %(levelname)s | %(funcName)s |  %(message)s",
            datefmt="%Y-%m-%d %I:%M:%S %p"
        )


#   Reload settings and receiver when clicking Save Settings in the Chatbot
def ReloadSettings(data):
    logging.debug("Saving new settings from SL Chatbot GUI.")
    global redemption_receiver
    try:
        # Reload settings
        script_settings.__dict__ = json.loads(data)
        script_settings.Save(SETTINGS_PATH)

        Unload(settings_reload=True)
        Start()
        logging.debug("Settings saved and applied successfully.")
    except Exception as e:
        logging.critical(traceback.print_exc())
        raise e
    return


#   Init called on script load. <Required>
def Init():
    log("FlagTracker script loading. Please see " + LOG_PATH + " for additional logging.")
    # Initialize Settings
    global script_settings
    script_settings = Settings(SETTINGS_PATH)
    script_settings.Save(SETTINGS_PATH)

    global is_stream_live
    # Update live state
    if Parent.IsLive():
        is_stream_live = True
    else:
        is_stream_live = False

    # Initialize Redemption Receiver
    Start()
    load_redemptions()
    return


def Unload(settings_reload=False):
    # Disconnect EventReceiver cleanly
    logging.info("Redemption event listener being disconnected.")
    try:
        global script_settings
        if not script_settings.RetainLogFiles:
            delete_log_files(create_new_logs=settings_reload)

        global redemption_receiver
        if redemption_receiver:
            redemption_receiver.Disconnect()
            logging.info("Redemption event listener disconnected.")
    except:
        logging.info("Event receiver already disconnected")
    return


def Start():
    global redemption_receiver
    redemption_receiver = TwitchPubSub()
    redemption_receiver.OnPubSubServiceConnected += event_receiver_connected
    redemption_receiver.OnRewardRedeemed += event_receiver_reward_redeemed
    redemption_receiver.OnPubSubServiceClosed += event_receiver_disconnected
    redemption_receiver.OnStreamUp += on_channel_live
    redemption_receiver.OnStreamDown += on_channel_offline
    redemption_receiver.Connect()
    return


def event_receiver_connected(sender, e):
    try:
        #  Get Channel ID for Username
        headers = {
            "Client-ID": "7a4xexuuxvxw5jmb9httrqq9926frq",
            "Authorization": "Bearer " + script_settings.TwitchOAuthToken
        }
        if not Parent.GetChannelName():
            # Sometimes the parent is not initialized at this point, so we wait a moment.
            sleep(2)
        result = json.loads(Parent.GetRequest("https://api.twitch.tv/helix/users?login=" +
                                              Parent.GetChannelName(), headers))
        logging.debug("Receiver connection result: " + str(result))
        if "error" in result.keys():
            if result["error"] == "Unauthorized":
                global validity_warning_issued
                if not validity_warning_issued:
                    post("Flagtracker: The script is not authorized to listen for redemptions on this channel. "
                         "Please ensure you have a valid oAuth key in the script settings.")
                    validity_warning_issued = True
            else:
                post("Flagtracker: Unexpected error connecting to channel. See log files for more details.")
                logging.critical("oAuth connection attempt error: " + str(result["error"]))
            global redemption_receiver
            redemption_receiver = None
            return

        user = json.loads(result["response"])
        user_id = user["data"][0]["id"]
        redemption_receiver.ListenToRewards(user_id)
        redemption_receiver.SendTopics(script_settings.TwitchOAuthToken)

        global script_uptime, is_reconnect
        script_uptime = datetime.now()
        if not is_reconnect:
            post("Flagtracker: Twitch Connection Established.")
            is_reconnect = True
        else:
            post("Flagtracker: Reconnected to Twitch.")

        return
    except Exception as e:
        logging.critical(str(e))


def event_receiver_reward_redeemed(sender, e):
    logging.debug("Redemption detected: " + str(e.RewardTitle))
    try:
        logging.debug("Channel point reward " + str(e.RewardTitle) +
                      " has been redeemed with status " + str(e.Status) +
                      ". Checking redemption name against list of redemptions.")
        try:
            for name in [name.strip().lower() for name in script_settings.TwitchRewardNames.split(",")]:
                if str(e.RewardTitle).lower() == name:
                    logging.debug("Redemption matches " + name)
                else:
                    logging.debug("Redemption does not match " + name)
        except Exception as ex:
            logging.debug(str(ex))

        logging.debug("Processing redemption.")
        if str(e.RewardTitle).lower() in \
                [name.strip().lower() for name in script_settings.TwitchRewardNames.split(",")]:
            logging.debug("Redemption has status " + str(e.Status).lower())
            if str(e.Status).lower() == "unfulfilled":
                logging.debug("Starting thread to add the redemption.")
                redemption_thread_queue.append(
                    threading.Thread(
                        target=reward_redeemed_worker,
                        args=(e.RewardTitle, e.Message, e.DisplayName)
                    )
                )
            elif str(e.Status).lower() == "action_taken":
                # Redemption is being removed from the Twitch dashboard. Iterate through redemptions and see if there
                # is a matching redemption in the queue that can be automatically removed.
                logging.debug("Attempting to remove finished redemption from queue.")
                for i in range(len(redemptions)):
                    if redemptions[i].Username == e.DisplayName and redemptions[i].Message == e.Message:
                        logging.debug("Matching redemption found.")
                        redemptions.pop(i)
                        save_redemptions()
                        logging.debug("Redemption at index " + str(i) + " automatically removed from the queue.")
                        return
                logging.debug("No matching redemption found.")
            else:
                logging.debug("Redemption is the wrong status. Skipping.")
        else:
            logging.debug("Redemption is the wrong reward name. Skipping.")
    except Exception as e:
        logging.critical(str(e))
    return


def event_receiver_disconnected(sender, e):
    if e:
        post("FlagTracker: Connection to Twitch lost. See logs for error message.")
        logging.error("Disconnect error: " + str(e))
    else:
        logging.debug("Connection to Twitch lost. No error was recorded, so this is probably fine.")
    global script_uptime, redemption_receiver
    script_uptime = None
    redemption_receiver = None


def on_channel_live(sender, e):
    global next_reconnect_attempt, next_token_validity_check
    logging.debug("Channel has gone live!")
    next_reconnect_attempt = datetime.now() + timedelta(minutes=1)
    next_token_validity_check = datetime.now() + timedelta(minutes=script_settings.TokenValidityCheckInterval)

    if script_settings.TwitchOAuthToken:
        logging.debug("Checking token status.")
        try:
            results = json.loads(Parent.GetRequest("https://id.twitch.tv/oauth2/validate",
                                                   {
                                                       "Authorization": "OAuth " + script_settings.TwitchOAuthToken
                                                   }
                                                   ))
            global script_uptime
            global redemption_receiver
            if results["status"] == 200:
                if script_uptime:
                    post("Flagtracker: Welcome back! The script has been connected to the "
                         "channel for " + calculate_time_difference(script_uptime))
                else:
                    logging.debug("The Twitch oAuth token is valid, but somehow the script_uptime is None.")
                    if redemption_receiver:
                        redemption_receiver.Disconnect()
                        logging.debug("Additionally, the script receiver exists.")
            else:
                global validity_warning_issued
                post("Flagtracker: Welcome back! The current token is not valid and needs to be refreshed.")
                validity_warning_issued = True
                if redemption_receiver:
                    redemption_receiver.Disconnect()
                elif script_uptime:
                    script_uptime = None
        except Exception as ex:
            logging.error("Exception when checking token validity: " + str(ex))
    else:
        logging.debug("No token existed. Skipping token validity check.")


def on_channel_offline():
    global next_token_validity_check, next_reconnect_attempt
    next_reconnect_attempt = datetime.now() + timedelta(days=365)
    next_token_validity_check = datetime.now() + timedelta(days=365)


def reward_redeemed_worker(reward, message, data_username):
    try:
        logging.debug("Processing " + reward + " redemption from " + data_username + " with message " + message)

        # When a person redeems,
        # only a reward name and message is supplied. Attempt to detect which game is being redeemed
        # for by scanning the message for keywords
        new_game = detect_game(reward, message)
        logging.debug("Redemption most closely matches game " + new_game + ".")

        # Create the new redemption object, append it to the list of redemptions, and save to file
        # (and Google Sheets, if enabled)
        logging.debug("Making redemption.")
        new_redemption = Redemption(Username=data_username, Game=new_game, Message=message)
        global redemptions
        redemptions.append(new_redemption)
        save_redemptions()
        logging.debug("Redemption added and saved.")
        if script_settings.EnableResponses:
            post("Flagtracker: Thank you for redeeming " +
                 reward + ", " + data_username + ". Your game has been added to the queue.")

        global next_reconnect_attempt
        next_reconnect_attempt = datetime.now() + timedelta(0, 0)

    except Exception as e:
        logging.critical(str(e))
    return


#   Opens readme file <Optional - DO NOT RENAME>
def openreadme():
    logging.debug("Opening readme file.")
    os.startfile(README_PATH)
    return


#   Opens Twitch.TV website to ask permissions
def get_token():
    logging.debug("Opening twitch web page to authenticate.")
    os.startfile("https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=7a4xexuuxvxw5jmb9httrqq9926frq"
                 "&redirect_uri=https://twitchapps.com/tokengen/&scope=channel:read:redemptions&force_verify=true")


#   Helper method to log
def log(message):
    Parent.Log(ScriptName, message)


#   Helper method to post to Twitch Chat
def post(message):
    Parent.SendStreamMessage(message)


def save_redemptions():
    try:
        # if the redemptions file does not exist, create it
        if not os.path.exists(REDEMPTIONS_PATH):
            logging.error("Redemptions.json did not exist.")
            with io.open(REDEMPTIONS_PATH, 'w') as outfile:
                outfile.write(json.dumps({}))
                logging.info("Redemptions.json has been created.")

        # record the redemptions
        logging.debug("Writing redemption objects to redemptions.json file.")
        with open(REDEMPTIONS_PATH, 'w') as outfile:
            outfile.seek(0)
            # When writing the Questions to disk, use the Question.toJSON() function
            json.dump(redemptions, outfile, indent=4, default=lambda q: q.to_json())
            outfile.truncate()
            logging.info("Redemptions saved to redemptions.json.")

        # Because of chatbot limitations, a secondary, external script is run to take the json file and upload
        # the redemption information to a Google Sheet. The settings file is shared between scripts.
        if script_settings.EnableGoogleSheets:
            logging.debug("Google Sheets is enabled. Running GoogleSheetsUpdater.exe.")
            update_google_sheet()
    except OSError as e:
        logging.critical(str(e))


def load_redemptions():
    # Ensure the questions file exists
    if os.path.exists(REDEMPTIONS_PATH):
        try:
            with open(REDEMPTIONS_PATH, "r") as infile:
                logging.debug("Loading object data from redemptions.json.")
                object_data = json.load(infile)  # Load the json data

                # For each object/question in the object_data, create new questions and feed them to the questions_list
                logging.debug("Creating redemption objects from the object data.")
                for redemption in object_data:
                    redemptions.append(
                        Redemption(
                            Username=redemption["Username"],
                            Game=redemption["Game"],
                            Message=redemption["Message"]
                        )
                    )
                logging.info(str(len(redemptions)) + " redemption(s) loaded from redemptions.json")
        except Exception as e:
            if not isinstance(e, ValueError):
                logging.critical(str(e.message))
    else:
        logging.info("No redemptions file detected. Creating one.")
        open(REDEMPTIONS_PATH, "w").close()


def get_attribute(attribute, message):
    attribute = attribute.lower() + ":"
    # The start index of the attribute begins at the end of the attribute designator, such as "game:"
    try:
        index_beginning_of_attribute = message.lower().index(attribute) + len(attribute)
    except ValueError as e:
        raise e
    # The end index of the attribute is at the last space before the next attribute designator,
    # or at the end of the message
    try:
        index_end_of_attribute = message[index_beginning_of_attribute:index_beginning_of_attribute +
                                                                      message[index_beginning_of_attribute:].index(
                                                                          ":")].rindex(",")
    except ValueError:
        # If this error is thrown, the end of the message was hit, so just return all of the remaining message
        return message[index_beginning_of_attribute:].strip()
    return message[index_beginning_of_attribute:index_beginning_of_attribute +
                                                index_end_of_attribute].strip().strip(",")


def get_user_id(raw_data):
    # Retrieves the user ID of a Twitch chatter using the raw data returned from Twitch
    try:
        raw_data = raw_data[raw_data.index("user-id=") + len("user-id="):]
        raw_data = raw_data[:raw_data.index(";")]
    except Exception:
        return ""
    return raw_data


def detect_game(reward, message):
    message = str(message).lower().strip().replace(" ", "").replace(":", "")
    logging.debug("Beginning game detection.")
    detected_game = {"game": "Unknown", "likelihood": 0}
    game_information = {
        "Timespinner": {
            "keywords": {
                "Timespinner": 5,
                "Lunais": 5,
                "Meyef": 5,
                "Cantoran": 5,
                "Talaria": 5,
                "Eye Spy": 4,
                "Gyre": 3,
                "Downloadable": 2,
                "Orbs": 2,
                "Fragile": 2,
                "Stinky": 2,
                "Jewelry": 2,
                "Inverted": 1,
                "Lore": 1,
                "Deathlink": 1,
                "TS": 1
            },
            "likelihood": 0
        },
        "Castlevania: SOTN Randomizer": {
            "keywords": {
                "Symphony of the Night": 5,
                "SOTN": 5,
                "empty hand": 2,
                "empty-hand": 2,
                "gem farmer": 2,
                "gem-farmer": 2,
                "scavenger": 1,
                "adventure mode": 1,
                "safe mode": 1
            },
            "likelihood": 0
        },
        "Chrono Trigger: Jets of Time Randomizer": {
            "keywords": {
                "Trigger": 3,
                "Chrono": 3,
                "Crono": 3,
                "Ayla": 3,
                "Marle": 3,
                "Frog": 3,
                "Lucca": 3,
                "Robo": 3,
                "Magus": 3,
                "Jets of Time": 5,
                "JoT": 2
            },
            "likelihood": 0
        },
        "Community's Choice": {
            "keywords": {
                "Chat": 3,
                "Community": 3,
                "Choice": 3,
                "Viewer": 3
            },
            "likelihood": 0
        },
        "Golden Sun: TLA Randomizer": {
            "keywords": {
                "TLA": 2,
                "The Lost Age": 5
            },
            "likelihood": 0
        },
        "FFIV: Free Enterprise": {
            "keywords": {
                "FE": 1,
                "FF4FE": 3,
                "Free Enterprise": 5,
                "FFIV": 3,
                "FF4": 3,
                "whichburn": 3,
                "kmain": 3,
                "ksummon": 3,
                "kmoon": 3,
                "ktrap": 3,
                "spoon": 2,
                "wincrystal": 3,
                "afflicted": 2,
                "battlescars": 3,
                "bodyguard": 2,
                "enemyunknown": 3,
                "musical": 2,
                "fistfight": 3,
                "floorislava": 3,
                "forwardisback": 3,
                "friendlyfire": 2,
                "gottagofast": 3,
                "batman": 2,
                "imaginarynumbers": 4,
                "isthisrandomized": 3,
                "kleptomania": 4,
                "menarepigs": 4,
                "biggermagnet": 5,
                "mysteryjuice": 4,
                "neatfreak": 4,
                "omnidextrous": 4,
                "payablegolbez": 5,
                "bigchocobo": 4,
                "sixleggedrace": 4,
                "skywarriors": 4,
                "worthfighting": 4,
                "tellahmaneuver": 5,
                "3point": 4,
                "timeismoney": 4,
                "unstackable": 2,
                "noadamants": 5,
                "draft": 3,
                "pushbtojump": 5,
                "supercannon": 4,
                "sealedcave": 2
            },
            "likelihood": 0
        },
        "FFVI: Beyond Chaos": {
            "keywords": {
                "BC": 2,
                "Beyond Chaos": 5,
                "FFVI BC": 5,
                "FF6 BC": 5,
                "johnnydmad": 3,
                "capslockoff": 2,
                "alasdraco": 3,
                "makeover": 1,
                "notawaiter": 2
            },
            "likelihood": 0
        },
        "FFVI: Worlds Collide": {
            "keywords": {
                "WC": 2,
                "Worlds Collide": 5,
                "FFVIWC": 5,
                "FF6WC": 5,
                "TimeForMemes": 1,
                "Terra": 2,
                "Relm": 2,
                "Umaro": 2,
                "Edgar": 2,
                "Shadow": 2,
                "Locke": 2,
                "Sabin": 2,
                "Strago": 2,
                "Gau": 2
            },
            "likelihood": 0
        },
        "FFV: Career Day": {
            "keywords": {
                "FFV": 2,
                "FF5": 2,
                "Career": 1,
                "FFVCD": 5,
                "FF5CD": 5,
                "Final Fantasy 5": 2,
                "Final Fantasy V": 2,
                "Galuf": 2,
                "Cara": 2,
                "Faris": 2,
                "Butz": 2,
                "Lenna": 2,
                "Krile": 2
            },
            "likelihood": 0
        },
        "Secret of Mana Randomizer": {
            "keywords": {
                "Secret of Mana": 5,
                "Mana": 3,
                "SoM Rando": 3,
                "SoM": 1,
                "Secret": 1,
            },
            "likelihood": 0
        },
        "SMRPG Randomizer": {
            "keywords": {
                "SMRPG": 5,
                "Culex": 3,
                "Mallow": 2,
                "Geno": 2,
                "Cspjl": 2,
                "Super": 1,
                "Mario": 1,
                "RPG": 1,
                "Peach": 1,
                "fakeout": 1
            },
            "likelihood": 0
        },
        "Streamer's Choice": {
            "keywords": {
                "Streamer": 3,
                "Strimmer": 3,
                "Choice": 3
            },
            "likelihood": 0
        },
        "Super Mario 3 Randomizer": {
            "keywords": {
                "Super Mario 3": 5,
                "Mario 3": 3,
                "SM3": 3,
                "SM3R": 3
            },
            "likelihood": 0
        },
        "Zelda 1 Randomizer": {
            "keywords": {
                "Zelda 1": 5,
                "Z1R": 5,
                "Z1": 3,
                "First Quest": 3,
                "Second Quest": 3,
                "1st Quest": 3,
                "2nd Quest": 3,
                "Mixed Quest": 3,
                "Boomstick": 3,
                "Shapes": 2,
                "Bubble": 2,
                "Candle": 2,
                "Armos": 2,
                "WhiteSword": 2,
                "Ladder": 2,
                "Book": 2,
                "Ganon": 2,
            },
            "likelihood": 0
        },
        "Zelda 3: LTTP Randomizer": {
            "keywords": {
                "LTTP": 5,
                "Link to the Past": 5,
                "Z3R": 5,
                "Zelda3": 5,
                "Shopsanity": 2,
                "Pedestal": 2,
                "Assured": 2,
                "Ganon": 2,
                "Armos": 2,
                "Deathlink": 1,
            },
            "likelihood": 0
        },
    }

    def add_likelihood(detected_game, new_game, new_game_data, likelihood_value):
        previous_likelihood_value = new_game_data["likelihood"]
        game_data["likelihood"] = game_data["likelihood"] + likelihood_value
        logging.debug("Game " + new_game + " likelihood value: " +
                      str(previous_likelihood_value) + " -> " + str(new_game_data["likelihood"]))
        if game_data["likelihood"] > detected_game["likelihood"]:
            detected_game["game"] = game
            detected_game["likelihood"] = game_data["likelihood"]
            logging.debug("Game " + game + " has the new highest likelihood.")
        elif game_data["likelihood"] == detected_game["likelihood"]:
            detected_game["game"] = detected_game["game"] + " or " + game
            logging.debug("Game " + game + " has tied the highest likelihood.")

    logging.debug("Game dict created.")
    try:
        for game, game_data in game_information.iteritems():
            # Check for the presence of the game name in the reward title
            if reward and game in reward:
                logging.debug("Game " + game + " matches redemption reward " + reward + ".")
                add_likelihood(detected_game, game, game_data, 10)

            logging.debug("Iterating over game " + game)
            if "keywords" in game_data:
                for keyword, value in game_data["keywords"].iteritems():
                    # Check for the presence of the keyword in the message
                    logging.debug("Iterating over key word " + keyword)
                    if keyword.lower().strip().replace(" ", "").replace(":", "") in message:
                        logging.debug("Redemption matches keyword '" + keyword + "' under game "
                                      + game + " based on message " + message)
                        if "likelihood" in game_data:
                            add_likelihood(detected_game, game, game_data, value)
                    else:
                        logging.debug("Key word " + keyword + " not found in message " + message)
    except Exception as ex:
        logging.debug(str(ex))
        return "Unknown"
    logging.debug("Returning new game " + detected_game["game"])
    return detected_game["game"]


def calculate_time_difference(time):
    response = ""
    if script_uptime:
        seconds_in_day = 86400
        seconds_in_hour = 3600
        seconds_in_minute = 60
        current_time = datetime.now()
        time_delta_in_seconds = abs((current_time - time).total_seconds())
        if time_delta_in_seconds >= seconds_in_day:
            response += str(int(time_delta_in_seconds / seconds_in_day)) + " days"
            time_delta_in_seconds = time_delta_in_seconds % seconds_in_day
        if time_delta_in_seconds >= seconds_in_hour:
            if len(response) > 0:
                response += ", "
            response += str(int(time_delta_in_seconds / seconds_in_hour)) + " hours"
            time_delta_in_seconds = time_delta_in_seconds % seconds_in_hour
        if time_delta_in_seconds >= seconds_in_minute:
            if len(response) > 0:
                response += ", "
            response += str(int(time_delta_in_seconds / seconds_in_minute)) + " minutes"
            time_delta_in_seconds = time_delta_in_seconds % seconds_in_minute
        if time_delta_in_seconds >= 0:
            if len(response) > 0:
                response += ", "
            response += str(int(time_delta_in_seconds)) + " seconds"
            # time_delta_in_seconds = time_delta_in_seconds % seconds_in_minute

        response += "."

    return response


def update_google_sheet():
    # If the token json exists, check the expiry
    if script_settings.SpreadsheetID == "" or script_settings.Sheet == "":
        logging.error("Error: No Spreadsheet ID and Sheet exist in Script Settings.")
        return
    logging.debug(GOOGLE_UPDATER_PATH)
    updater_thread = threading.Thread(
        target=os.system,
        args=('"' + GOOGLE_UPDATER_PATH + '"',)
    )
    updater_thread.daemon = True
    updater_thread.start()


if __name__ == "__main__":
    args = raw_input("Enter the game name: ")

    print("Argument: " + args)
    print("Detected game: " + detect_game(args))
