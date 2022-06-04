# -*- coding: utf-8 -*-

import clr
import codecs
import datetime
import io
import json
import os
import re
import sys
import threading
import traceback
# Importing Required Libraries
from re import search, compile

sys.platform = "win32"
# Try/Except here to avoid exceptions when __main__ code at the bottom
try:
    clr.AddReference("IronPython.Modules.dll")
    clr.AddReferenceToFileAndPath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                               "References",
                                               "TwitchLib.PubSub.dll"))
    from TwitchLib.PubSub import TwitchPubSub
except:
    pass

#   Script Information <Required>
ScriptName = "FlagTracker"
Website = "https://www.twitch.tv/Crimdahl"
Description = "Tracks User Flag Redemptions by writing to json file."
Creator = "Crimdahl"
Version = "1.2.8-Beta"

#   Define Global Variables <Required>
SCRIPT_PATH = os.path.dirname(__file__)
GOOGLE_UPDATER_PATH = os.path.join(SCRIPT_PATH, "GoogleSheetsUpdater.exe")
SETTINGS_PATH = os.path.join(SCRIPT_PATH, "settings.json")
README_PATH = os.path.join(SCRIPT_PATH, "Readme.md")
LOG_PATH = os.path.join(SCRIPT_PATH, "flagtrackerlog.txt")
REDEMPTIONS_PATH = os.path.join(SCRIPT_PATH, "redemptions.json")
TOKEN_PATH = os.path.join(SCRIPT_PATH, "token.json")

script_settings = None
log_file = None
redemptions = []

event_receiver = None
thread_queue = []
thread = None
play_next_at = datetime.datetime.now()


# Define Redemptions
class Redemption(object):
    def __init__(self, **kwargs):
        self.Username = kwargs["Username"] if "Username" in kwargs else "Unknown"
        self.Game = kwargs["Game"] if "Game" in kwargs else "Unknown"
        self.Message = kwargs["Message"] if "Message" in kwargs else "Unknown"

    def toJSON(self):
        return {"Username": self.Username, "Game": self.Game, "Message": self.Message}

    def setGame(self, value):
        self.Game = value

    def setUsername(self, value):
        self.Username = value

    def setMessage(self, value):
        self.Message = value
    

# Define Settings. If there is no settings file created, then use default values in else statement.
class Settings(object):
    def __init__(self, SettingsPath=None):
        if SettingsPath and os.path.isfile(SettingsPath):
            with codecs.open(SettingsPath, encoding="utf-8-sig", mode="r") as f:
                self.__dict__ = json.load(f, encoding="utf-8")
        else:
            #Output Settings
            self.EnableDebug = True
            self.EnableResponses = True
            self.DisplayMessageOnGameUnknown = False
            self.RunCommandsOnlyWhenLive = True
            self.DisplayPermissions = "Everyone"
            self.ModifyPermissions = "Moderator"
            self.CommandName = "queue"
            self.DisplayLimit = "10"

            #Twitch Settings
            self.TwitchOAuthToken = ""
            self.TwitchRewardNames = ""

            #Google Sheets Settings
            self.EnableGoogleSheets = False
            self.ExpiredTokenAction = "Nothing"
            self.SpreadsheetID = ""
            self.Sheet = ""

    def Reload(self, jsondata):
        self.__dict__ = json.loads(jsondata, encoding="utf-8")
        return

    def Save(self, SettingsPath):
        try:
            with codecs.open(SettingsPath, encoding="utf-8-sig", mode="w+") as f:
                json.dump(self.__dict__, f, encoding="utf-8")
        except Exception as e:
            log("Failed to save settings to the file: " + str(e))
        return


#   Process messages <Required>
def Execute(data):
    user_id = get_user_id(data.RawData)

    # Check if the streamer is live. Still run commands if the script is set to run while offline
    if Parent.IsLive() or not script_settings.RunCommandsOnlyWhenLive:
        # Check if the message begins with "!" and the command name AND the user has permissions to run the command
        if (str(data.Message).startswith("!" + script_settings.CommandName) and data.GetParamCount() == 1
            and (Parent.HasPermission(data.User, script_settings.DisplayPermissions, "")
                 or user_id == "216768170")):
            log_to_file("[EXECUTE - NO ARG] Received.")
            # If the user is using Google Sheets, post a link to the Google Sheet in chat
            if script_settings.EnableGoogleSheets and script_settings.SpreadsheetID != "":
                log_to_file("[EXECUTE - NO ARG] Displaying Google Sheets link.")
                post("https://docs.google.com/spreadsheets/d/" + script_settings.SpreadsheetID)
                return
            # If the user is not using Google Sheets, read lines from the json file in the script directory
            else:
                log_to_file("[EXECUTE - NO ARG] Displaying redemptions in chat.")
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
                    post("The community queue is empty!")
        elif (str.startswith(data.Message, "!" + script_settings.CommandName + " find")
                and (Parent.HasPermission(data.User, script_settings.DisplayPermissions, "")
                     or user_id == "216768170")):
            log_to_file("[EXECUTE - FIND] Received.")
            if data.GetParamCount() < 4:
                if data.GetParamCount() == 2:
                    #No username supplied. Search for redemptions by the user that posted the command.
                    search_username = data.User
                else: 
                    #Username supplied. Search for redemptions by the supplied username
                    search_username = data.GetParam(2)
                log_to_file("[EXECUTE - FIND] Searching for user " + str(search_username) + ".")
                index = 1
                found = False
                for redemption in redemptions:
                    if str(redemption.Username).lower() == str(search_username).lower():
                        log_to_file("[EXECUTE - FIND] Redemption found at index " + str(index) + ".")
                        if script_settings.DisplayMessageOnGameUnknown and \
                                str(redemption.Game).lower().strip() == "unknown":
                            post(str(index) + ") " + redemption.Username + " - " + redemption.Message)
                        else:
                            post(str(index) + ") " + redemption.Username + " - " + redemption.Game)
                        found = True
                    index = index + 1
                if not found:
                    log_to_file("[EXECUTE - FIND] No redemptions found for username " + search_username + ".")
                    post("No redemptions were found for the username " + search_username + ".")
                return
            else:
                log_to_file("[EXECUTE - FIND] Too many parameters: " +
                            str(data.GetParamCount()))
                if script_settings.EnableResponses:
                    post("Usage: !" + script_settings.CommandName + " find <Optional Username>")
        # Check if the user is attempting to remove an item from the queue.
        # Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + script_settings.CommandName + " remove")
                and (Parent.HasPermission(data.User, script_settings.ModifyPermissions, "")
                     or user_id == "216768170")):
            log_to_file("[EXECUTE - REMOVE] Received.")
            # Check if the supplied information has three or more parameters: !command, remove, and one or more indices
            if data.GetParamCount() >= 3: 
                log_to_file("[EXECUTE - REMOVE] Removing the redemption(s)")
                data_string = str(data.Message)
                # Separate the indices from the rest of the message and split them by comma delimiter
                data_array = data_string[data_string.index("remove") + len("remove"):].replace(" ", "").split(",")
                # It is necessary to remove them from lowest index to highest index, so sort the indices first
                # Should I just remove from highest to lowest?
                data_array.sort()
                if script_settings.EnableDebug:
                    log("Removing the following indexes from Redemptions: " + str(data_array))
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
                    log_to_file("[EXECUTE - REMOVE] Success.")
                    if script_settings.EnableResponses:
                        post("Redemption(s) successfully removed from the queue.")
                except (ValueError, IndexError) as e:
                    # Log an error if the index is either a non-integer or is outside of the range of the redemptions
                    if script_settings.EnableDebug:
                        log("Error: " + e.message)
                    if isinstance(e, IndexError):
                        if script_settings.EnableResponses:
                            post("Error: Supplied index was out of range. The valid range is 1-" +
                                 str(len(redemptions)) + ".")
            else:
                # If the supplied command is just "!<command name> remove" and chat responses are enabled,
                # display the command usage text in chat.
                log_to_file("[EXECUTE - REMOVE] Insufficient parameters.")
                if script_settings.EnableResponses:
                    post("Usage: !" + script_settings.CommandName + " remove <Comma-Separated Integer Indexes>")
        # Check if the user is attempting to add an item to the queue.
        # Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + script_settings.CommandName + " add")
                and (Parent.HasPermission(data.User, script_settings.ModifyPermissions, "")
                     or user_id == "216768170")):
            log_to_file("[EXECUTE - ADD] Received.")
            # Check if the supplied information has three or more parameters:
            # !command, add, and one or more sets of information
            if data.GetParamCount() >= 3: 
                log_to_file("[EXECUTE - ADD] Adding redemption(s)")
                data_string = str(data.Message)
                # Separate the information sets from the rest of the message and split them by pipe delimiter
                data_array = data_string[data_string.index("add") + len("add"):].split("|")
                redemptions_added = 0
                for info in data_array:
                    if script_settings.EnableDebug:
                        log("Adding new redemption via add command: " + str(info))
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
                            pass

                        if "index:" in info:
                            redemptions.insert(int(get_attribute("Index", info)) - 1,
                                               Redemption(Username=new_user, Message=new_message, Game=new_game))
                            redemptions_added = redemptions_added + 1
                        else:        
                            redemptions.append(Redemption(Username=new_user, Message=new_message, Game=new_game))
                            redemptions_added = redemptions_added + 1
                    except (AttributeError, ValueError) as e:
                        if script_settings.EnableDebug: log("Error encountered when adding redemptions: " + e.message)
                        continue
                # Save the new redemptions. This method also saves to Google Sheets if enabled,
                # so no additional logic is required to add entries to Google Sheets.
                if redemptions_added > 0:
                    save_redemptions()
                    log_to_file("[EXECUTE - ADD] Success.")
                    if script_settings.EnableResponses:
                        post("Successfully added " + str(redemptions_added) + " redemption(s) to the queue.")
                else:
                    log_to_file("[EXECUTE - ADD] Failure.")
                    if script_settings.EnableResponses:
                        post("Failed to add redemptions to the queue.")
            else:
                # If the supplied command is just "!<command name> remove" and chat responses are enabled,
                # display the command usage text in chat.
                log_to_file("[EXECUTE - ADD] Insufficient parameters.")
                if script_settings.EnableResponses:
                    post("Usage: !" + script_settings.CommandName +
                         " add Username:<UserName>, Message:<Message>, (Game:<Game>) | Username:<UserName>, ...")
        # Check if the user is attempting to edit an item in the queue.
        # Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + script_settings.CommandName + " edit")
                and (Parent.HasPermission(data.User, script_settings.ModifyPermissions, "")
                     or user_id == "216768170")):
            log_to_file("[EXECUTE - EDIT] Received.")
            # This command takes 3 or more parameters: !<command name>, an index, and attributes to edit at that index
            if data.GetParamCount() >= 3: 
                try:
                    changes = False
                    # Get the index and a set of comma-separated attributes from the message
                    index = int(data.GetParam(2))
                    data = str(data.Message)[len("!" + script_settings.CommandName + " edit " + str(index)):].split("|")
                    target = redemptions[index - 1]

                    # Attempt to modify each type of attribute. Do nothing if the attribute is not found.
                    # Save only if changes happen.
                    for attribute in data:
                        if "username" in attribute.lower():
                            try:
                                target.setUsername(get_attribute("Username", attribute))
                                changes = True
                            except (AttributeError, ValueError) as e:
                                if script_settings.EnableDebug:
                                    log("Error encountered when editing redemption username: " + e.message)
                        if "message" in attribute.lower():
                            try:
                                target.setMessage(get_attribute("Message", attribute))
                                changes = True
                            except (AttributeError, ValueError) as e:
                                if script_settings.EnableDebug:
                                    log("Error encountered when editing redemption message: " + e.message)
                        if "game" in attribute.lower():
                            try:
                                target.setGame(get_attribute("Game", attribute))
                                changes = True
                            except (AttributeError, ValueError) as e:
                                if script_settings.EnableDebug:
                                    log("Error encountered when editing redemption game: " + e.message)
                    # Save the modified redemptions. This method also saves to Google Sheets if enabled,
                    # so no additional logic is required to modify entries in Google Sheets.
                    if changes: 
                        save_redemptions()
                        log_to_file("[EXECUTE - EDIT] Success.")
                        if script_settings.EnableResponses:
                            post("Queue successfully modified.")
                    else:
                        log_to_file("[EXECUTE - EDIT] Failure.")
                except (ValueError, IndexError) as e:
                    if script_settings.EnableDebug:
                        log("Error encountered when editing redemption: " + e.message)
            else:
                log_to_file("[EXECUTE - EDIT] Insufficient parameters.")
                if script_settings.EnableResponses:
                    post("Usage: !" + script_settings.CommandName +
                         " edit <Index> <Username/Game/Message>:<Value>(|<Username/Game/Message>:<Value>|...)")
        elif (str.startswith(data.Message, "!" + script_settings.CommandName + " updater")
              and (Parent.HasPermission(data.User, script_settings.ModifyPermissions, "")
                   or user_id == "216768170")):
            log_to_file("[EXECUTE - UPDATER] Received.")
            if script_settings.EnableGoogleSheets:
                update_google_sheet()
                post("Google Sheets Updater executed. "
                     "If no change occurs, the Google Sheets oAuth token may be expired.")
                log_to_file("[EXECUTE - UPDATER] Success?")
            else:
                log_to_file("[EXECUTE - UPDATER] Failed - Google Sheets Disabled.")


# [Required] Tick method (Gets called during every iteration even when there is no incoming data)
def Tick():
    global play_next_at
    if play_next_at > datetime.datetime.now():
        return

    global thread
    if thread and not thread.isAlive():
        thread = None

    if thread is None and len(thread_queue) > 0:
        thread = thread_queue.pop(0)
        thread.start()

    return


#   Reload settings and receiver when clicking Save Settings in the Chatbot
def ReloadSettings(jsonData):
    log_to_file("[RELOAD SETTINGS] Saving new settings from SL Chatbot GUI.")
    if script_settings.EnableDebug:
        log("Saving new settings from SL Chatbot GUI.")
    global event_receiver
    try:
        # Reload settings
        script_settings.__dict__ = json.loads(jsonData)
        script_settings.Save(SETTINGS_PATH)

        unload()
        start()
        log_to_file("[RELOAD SETTINGS] Settings saved and applied successfully.")
        if script_settings.EnableDebug:
            log("Settings saved and applied successfully")
    except Exception as e:
        log_to_file("[RELOAD SETTINGS] Error encountered when saving settings: " + str(e))
        if script_settings.EnableDebug:
            log("Error encountered when saving settings: " + str(e))
    return


#   Init called on script load. <Required>
def Init():
    # Initialize Settings
    global script_settings
    log_to_file("\n\n")
    script_settings = Settings(SETTINGS_PATH)
    script_settings.Save(SETTINGS_PATH)
    
    # Initialize Redemption Receiver
    start()
    load_redemptions()
    return


def start():
    log_to_file("[RECEIVER START] Initializing receiver and connecting to Twitch channel")
    if script_settings.EnableDebug:
        log("Initializing receiver and connecting to Twitch channel")

    global event_receiver
    event_receiver = TwitchPubSub()
    event_receiver.OnPubSubServiceConnected += event_receiver_connected
    event_receiver.OnRewardRedeemed += event_receiver_reward_redeemed
    
    event_receiver.Connect()
    return


def event_receiver_connected(sender, e):
    #  Get Channel ID for Username
    headers = {
        "Client-ID": "7a4xexuuxvxw5jmb9httrqq9926frq",
        "Authorization": "Bearer " + script_settings.TwitchOAuthToken
    }
    result = json.loads(Parent.GetRequest("https://api.twitch.tv/helix/users?login=" + Parent.GetChannelName(), headers))
    log_to_file("[RECEIVER CONNECTED] Connection result: " + str(result))
    if script_settings.EnableDebug: log("Connection result: " + str(result))
    user = json.loads(result["response"])
    user_id = user["data"][0]["id"]
    log_to_file("[RECEIVER CONNECTED] Your User ID: " + str(user_id))

    event_receiver.ListenToRewards(user_id)
    event_receiver.SendTopics(script_settings.TwitchOAuthToken)
    log_to_file("[RECEIVER CONNECTED] event_receiver_connected method successfully completed.")
    return


def event_receiver_reward_redeemed(sender, e):
    try:
        log_to_file("[EVENT RECEIVER] Channel Point Redemption Triggered")
        log_to_file("[EVENT RECEIVER] List of attributes and methods in the event handler: " + str(dir(e)))
        log_to_file("[EVENT RECEIVER] Channel point reward " + str(e.RewardTitle) + " has been redeemed with status " + str(e.Status) + ".")
        if script_settings.EnableDebug:
            log("Channel point reward " + str(e.RewardTitle) + " has been redeemed with status " + str(e.Status) + ".")

        if str(e.Status).lower() == "unfulfilled" and str(e.RewardTitle).lower() in \
                [name.strip().lower() for name in script_settings.TwitchRewardNames.split(",")]:
            log_to_file("[EVENT RECEIVER] Unfulfilled redemption matches a reward name. Starting thread to add the redemption.")
            if script_settings.EnableDebug:
                log("Unfulfilled redemption matches a reward name. Starting thread to add the redemption.")

            thread_queue.append(
                threading.Thread(
                    target=reward_redeemed_worker,
                    args=(e.RewardTitle, e.Message, e.DisplayName)
                )
            )
        elif str(e.Status).lower() == "action_taken" and str(e.RewardTitle).lower() \
                in [name.strip().lower() for name in script_settings.TwitchRewardNames.split(",")]:
            # Redemption is being removed from the Twitch dashboard. Iterate through redemptions and see if there
            # is a matching redemption in the queue that can be automatically removed.
            log_to_file("[EVENT RECEIVER] Fulfilled redemption matches a reward name. "
                    "Attempting to auto-remove the redemption from the queue.")
            if script_settings.EnableDebug:
                log("Fulfilled redemption matches a reward name. Attempting to auto-remove the redemption from the queue.")
            for i in range(len(redemptions)):
                if redemptions[i].Username == e.DisplayName and redemptions[i].Message == e.Message:
                    redemptions.pop(i)
                    save_redemptions()
                    log_to_file("[EVENT RECEIVER] Redemption at index " + str(i) + " automatically removed from the queue.")
                    if script_settings.EnableDebug:
                        log("Redemption at index " + str(i) + " automatically removed from the queue.")
                    return
            log_to_file("[EVENT RECEIVER] No matching redemption found. Was it already removed from the queue?")
            if script_settings.EnableDebug:
                log("No matching redemption found. Was it already removed from the queue?")
        else:
            log_to_file("[EVENT RECEIVER] Redemption is the wrong status and reward name. Skipping.")
            if script_settings.EnableDebug:
                log("Redemption is the wrong status and reward name. Skipping.")
        log("event_receiver_reward_redeemed method successfully completed.")
    except Exception as ex:
        log_to_file("[EVENT RECEIVER] The reward handler encountered an unhandled exception of class " + str(type(ex)) + ".")
        log_to_file("[EVENT RECEIVER] Traceback: " + traceback.format_exc())
    return


def reward_redeemed_worker(reward, message, data_username):
    try:
        log_to_file("[REWARD WORKER THREAD] Thread started. Processing " + reward + " redemption from " + data_username + " with message " + message)
        if script_settings.EnableDebug:
            log("Thread started. Processing " + reward + " redemption from " + data_username + " with message " + message)

        # When a person redeems, only a reward name and message is supplied. Attempt to detect which game is being redeemed
        # for by scanning the message for keywords
        detection_string = str(reward + ' ' + message).lower().strip().replace(" ", "").replace(":", "")
        new_game = detect_game(detection_string)
        log_to_file("[REWARD WORKER THREAD] Redemption most closely matches game " + new_game + ".")

        # Create the new redemption object, append it to the list of redemptions, and save to file
        # (and Google Sheets, if enabled)
        new_redemption = Redemption(Username=data_username, Game=new_game, Message=message)
        redemptions.append(new_redemption)
        log_to_file("[REWARD WORKER THREAD] Saving new redemption.")
        save_redemptions()
        if script_settings.EnableResponses:
            post("Thank you for redeeming " + reward + ", " + data_username + ". Your game has been added to the queue.")
        
        global play_next_at
        play_next_at = datetime.datetime.now() + datetime.timedelta(0, 0)
        log_to_file("[REWARD WORKER THREAD] Successfully completed.")
    
    except Exception as ex:
        log_to_file("[REWARD WORKER THREAD] The reward worker thread encountered an unhandled exception of class " + str(type(ex)) + ".")
        log_to_file("[REWARD WORKER THREAD] Traceback: " + traceback.format_exc())
    return


def unload():
    # Disconnect EventReceiver cleanly
    log_to_file("[UNLOAD EVENT LISTENER] Redemption event listener being unloaded.")
    try:
        global event_receiver
        if event_receiver:
            event_receiver.Disconnect()
            log_to_file("[UNLOAD EVENT LISTENER] Redemption event listener unloaded.")
            event_receiver = None
    except:
        log_to_file("[UNLOAD EVENT LISTENER] Event receiver already disconnected")
    return


#   Opens readme file <Optional - DO NOT RENAME>
def openreadme():
    log_to_file("[OPEN README] Opening readme file.")
    os.startfile(README_PATH)
    return


#   Opens Twitch.TV website to ask permissions
def get_token():
    log_to_file("[GET TOKEN] Opening twitch web page to authenticate.")
    os.startfile("https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=7a4xexuuxvxw5jmb9httrqq9926frq"
                 "&redirect_uri=https://twitchapps.com/tokengen/&scope=channel:read:redemptions&force_verify=true")
    return


#   Helper method to log
def log(message):
    Parent.Log(ScriptName, message)


def log_to_file(line):
    global log_file
    log_file = open(LOG_PATH, "a+")
    log_file.writelines(str(datetime.datetime.now()) + " " + line + "\n")
    log_file.close()


#   Helper method to post to Twitch Chat
def post(message):
    Parent.SendStreamMessage(message)


def save_redemptions():
    try:        
        # if the redemptions file does not exist, create it
        if not os.path.exists(REDEMPTIONS_PATH):
            log_to_file("[SAVE REDEMPTIONS] Redemptions.json did not exist.")
            with io.open(REDEMPTIONS_PATH, 'w') as outfile:
                outfile.write(json.dumps({}))
                log_to_file("[SAVE REDEMPTIONS] Redemptions.json has been created.")

        # record the redemptions
        log_to_file("[SAVE REDEMPTIONS] Writing redemption objects to redemptions.json file.")
        with open (REDEMPTIONS_PATH, 'w') as outfile:
            outfile.seek(0)
            # When writing the Questions to disk, use the Question.toJSON() function
            json.dump(redemptions, outfile, indent=4, default=lambda q: q.toJSON())
            outfile.truncate()
            log_to_file("[SAVE REDEMPTIONS] Redemption objects written to redemptions.json.")

        # Because of chatbot limitations, a secondary, external script is run to take the json file and upload
        # the redemption information to a Google Sheet. The settings file is shared between scripts.
        if script_settings.EnableGoogleSheets:
            log_to_file("[SAVE REDEMPTIONS] Google Sheets is enabled. Running GoogleSheetsUpdater.exe.")
            update_google_sheet()
    except OSError as e:
        log("Error: Unable to save redemptions! " + e.message)


def load_redemptions():
    # Ensure the questions file exists
    log_to_file("[LOAD REDEMPTIONS] Loading redemptions from redemptions.json.")
    if os.path.exists(REDEMPTIONS_PATH):
        log_to_file("[LOAD REDEMPTIONS] Redemptions.json detected. Opening.")
        try:
            with open(REDEMPTIONS_PATH, "r") as infile:
                log_to_file("[LOAD REDEMPTIONS] Loading object data from redemptions.json.")
                object_data = json.load(infile)    # Load the json data

                # For each object/question in the object_data, create new questions and feed them to the questions_list
                log_to_file("[LOAD REDEMPTIONS] Creating redemption objects from the object data.")
                for redemption in object_data:
                    redemptions.append(
                        Redemption(
                            Username=redemption["Username"],
                            Game=redemption["Game"],
                            Message=redemption["Message"]
                        )
                    )
                log_to_file("[LOAD REDEMPTIONS] Redemptions successfully loaded from redemptions.json")
                if script_settings.EnableDebug: log("Redemptions loaded: " + str(len(redemptions)))
        except Exception as e:
            log_to_file("[LOAD REDEMPTIONS] ERROR loading redemptions from redemptions.json: " + str(e.message))
            if script_settings.EnableDebug: log("ERROR loading redemptions from redemptions.json: " + str(e.message))

    else:
        log_to_file("[LOAD REDEMPTIONS] No redemptions file detected. Creating one.")
        if script_settings.EnableDebug: log("WARNING: No redemptions file exists. Creating one.")
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
                                         message[index_beginning_of_attribute:].index(":")].rindex(",")
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


def detect_game(message):
    new_game = "Unknown"
    detection_string = str(message).lower().strip().replace(" ", "").replace(":", "")
    game_information = {
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
            "hits": 0
        },
        "Golden Sun: TLA Randomizer": {
            "keywords": {
                "TLA": 2,
                "The Lost Age": 5
            },
            "hits": 0
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
                "spoon": 1,
                "wincrystal": 1,
                "afflicted": 1,
                "battlescars": 2,
                "bodyguard": 1,
                "enemyunknown": 2,
                "musical": 1,
                "fistfight": 2,
                "floorislava": 2,
                "forwardisback": 2,
                "friendlyfire": 1,
                "gottagofast": 2,
                "batman": 1,
                "imaginarynumbers": 3,
                "isthisrandomized": 2,
                "kleptomania": 3,
                "menarepigs": 3,
                "biggermagnet": 4,
                "mysteryjuice": 3,
                "neatfreak": 3,
                "omnidextrous": 3,
                "payablegolbez": 5,
                "bigchocobo": 3,
                "sixleggedrace": 3,
                "skywarriors": 3,
                "worthfighting": 3,
                "tellahmaneuver": 5,
                "3point": 3,
                "timeismoney": 3,
                "unstackable": 1,
                "noadamants": 5,
                "draft": 2
            },
            "hits": 0
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
            "hits": 0
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
            "hits": 0
        },
        "Timespinner Randomizer": {
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
            "hits": 0
        },
        "Secret of Mana Randomizer": {
            "keywords": {
                "Secret of Mana": 5,
                "Secret": 1,
                "Mana": 3,
                "SoM Rando": 3,
                "SoM": 1,
            },
            "hits": 0
        },
        "SMRPG Randomizer": {
            "keywords": {
                "SMRPG": 5,
                "Super": 1,
                "Mario": 1,
                "RPG": 1,
                "Mallow": 2,
                "Geno": 2,
                "Cspjl": 2,
                "fakeout": 1
            },
            "hits": 0
        },
        "Streamer's Choice": {
            "keywords": {
                "Streamer": 1,
                "Choice": 1
            },
            "hits": 0
        },
        "Super Mario 3 Randomizer": {
            "keywords": {
                "Super Mario 3": 5,
                "Mario 3": 3,
                "SM3": 3,
                "SM3R": 3
            },
            "hits": 0
        },
        "Zelda 3: LTTP Randomizer": {
            "keywords": {
                "LTTP": 5,
                "Link to the Past": 5,
                "Pedestal": 2,
                "Assured": 2,
                "Z3R": 5,
                "Zelda3": 5
            },
            "hits": 0
        }
    }

    highest_hits = 0
    for game, game_data in game_information.iteritems():
        if "keywords" in game_data:
            for keyword, value in game_data["keywords"].iteritems():
                if keyword.lower().strip().replace(" ", "").replace(":", "") in detection_string:
                    if "hits" in game_data:
                        log_to_file("[GAME DETECTION] Redemption matches keyword '" + keyword + "' under game " + game)
                        game_data["hits"] = game_data["hits"] + value
                        log_to_file("[GAME DETECTION] " + game + " keyword value is " + str(game_data["hits"]))
                        if game_data["hits"] > highest_hits:
                            new_game = game
                            highest_hits = game_data["hits"]
                        elif game_data["hits"] == highest_hits:
                            new_game = new_game + " or " + game
    return new_game


def update_google_sheet():
    # If the token json exists, check the expiry
    # if script_settings.ExpiredTokenAction == "Chat Alert":
    #     if os.path.isfile(TOKEN_PATH):
    #         with open(TOKEN_PATH, 'rb') as token_file:
    #             token_json = json.loads(token_file.read().decode("utf-8-sig"))
    #             if 'expiry' in token_json:
    #                 token_expiry = datetime.datetime.strptime(token_json['expiry'], "%Y-%m-%dT%H:%M:%S.%fZ")
    #                 if token_expiry < datetime.datetime.now():
    #                     post("Alert: Your Flag Tracker Google Sheets token is expired.")
    #                     return
    if script_settings.SpreadsheetID == "" or script_settings.Sheet == "":
        log_to_file("[UPDATE GOOGLE SHEET] Error: No Spreadsheet ID and Sheet in Script Settings.")
        log("Error: You must enter a valid Spreadsheet ID and Sheet Name to use Google Sheets.")
        return
    threading.Thread(
        target=os.system,
        args=(GOOGLE_UPDATER_PATH,)
    ).start()


if __name__ == "__main__":
    args = raw_input("Enter the game name: ")

    print("Argument: " + args)
    print("Detected game: " + detect_game(args))
