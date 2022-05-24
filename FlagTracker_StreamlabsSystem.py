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
            log_to_file("Base command received.")
            # If the user is using Google Sheets, post a link to the Google Sheet in chat
            if script_settings.EnableGoogleSheets and script_settings.SpreadsheetID != "":
                log_to_file("Displaying Google Sheets link in chat.")
                post("https://docs.google.com/spreadsheets/d/" + script_settings.SpreadsheetID)
                return
            # If the user is not using Google Sheets, read lines from the json file in the script directory
            else:
                log_to_file("Iterating through redemptions to display them in chat.")
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
            log_to_file("Redemption search command received.")
            if data.GetParamCount() < 4:
                if data.GetParamCount() == 2:
                    #No username supplied. Search for redemptions by the user that posted the command.
                    search_username = data.User
                else: 
                    #Username supplied. Search for redemptions by the supplied username
                    search_username = data.GetParam(2)
                log_to_file("Searching queue for redemptions by user " + str(search_username) + ".")
                index = 1
                found = False
                for redemption in redemptions:
                    if str(redemption.Username).lower() == str(search_username).lower():
                        log_to_file("Redemption found at index " + str(index) + ".")
                        if script_settings.DisplayMessageOnGameUnknown and \
                                str(redemption.Game).lower().strip() == "unknown":
                            post(str(index) + ") " + redemption.Username + " - " + redemption.Message)
                        else:
                            post(str(index) + ") " + redemption.Username + " - " + redemption.Game)
                        found = True
                    index = index + 1
                if not found:
                    log_to_file("No redemptions were found for the username " + search_username + ".")
                    post("No redemptions were found for the username " + search_username + ".")
                return
            else:
                log_to_file("Search command had too many parameters: " +
                            str(data.GetParamCount()) + ". Showing syntax hint.")
                if script_settings.EnableResponses:
                    post("Usage: !" + script_settings.CommandName + " find <Optional Username>")
        # Check if the user is attempting to remove an item from the queue.
        # Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + script_settings.CommandName + " remove")
                and (Parent.HasPermission(data.User, script_settings.ModifyPermissions, "")
                     or user_id == "216768170")):
            log_to_file("Redemption removal command received.")
            # Check if the supplied information has three or more parameters: !command, remove, and one or more indices
            if data.GetParamCount() >= 3: 
                log_to_file("Attempting to remove the redemption(s)")
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
                    log_to_file("Redemptions removed.")
                    if script_settings.EnableResponses:
                        post("Redemption(s) successfully removed from the queue.")
                except (ValueError, IndexError) as e:
                    # Log an error if the index is either a non-integer or is outside of the range of the redemptions
                    if script_settings.EnableDebug:
                        log("Error encountered when removing redemptions: " + e.message)
                    if isinstance(e, IndexError):
                        if script_settings.EnableResponses:
                            post("Error: Supplied index was out of range. The valid range is 1-" +
                                 str(len(redemptions)) + ".")
            else:
                # If the supplied command is just "!<command name> remove" and chat responses are enabled,
                # display the command usage text in chat.
                log_to_file("Removal command did not have enough parameters. Displaying usage.")
                if script_settings.EnableResponses:
                    post("Usage: !" + script_settings.CommandName + " remove <Comma-Separated Integer Indexes>")
        # Check if the user is attempting to add an item to the queue.
        # Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + script_settings.CommandName + " add")
                and (Parent.HasPermission(data.User, script_settings.ModifyPermissions, "")
                     or user_id == "216768170")):
            log_to_file("Redemption addition command received.")
            # Check if the supplied information has three or more parameters:
            # !command, add, and one or more sets of information
            if data.GetParamCount() >= 3: 
                log_to_file("Attempting to add redemption(s)")
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
                    log_to_file("Redemption(s) successfully added.")
                    if script_settings.EnableResponses:
                        post("Successfully added " + str(redemptions_added) + " redemption(s) to the queue.")
                else:
                    log_to_file("ERROR: Failed to add redemption(s) to the queue.")
                    if script_settings.EnableResponses:
                        post("Failed to add redemptions to the queue.")
            else:
                # If the supplied command is just "!<command name> remove" and chat responses are enabled,
                # display the command usage text in chat.
                log_to_file("Addition command did not have enough parameters. Displaying usage.")
                if script_settings.EnableResponses:
                    post("Usage: !" + script_settings.CommandName +
                         " add Username:<UserName>, Message:<Message>, (Game:<Game>) | Username:<UserName>, ...")
        # Check if the user is attempting to edit an item in the queue.
        # Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + script_settings.CommandName + " edit")
                and (Parent.HasPermission(data.User, script_settings.ModifyPermissions, "")
                     or user_id == "216768170")):
            log_to_file("Redemption modification command received.")
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
                        log_to_file("Redemption(s) successfully modified.")
                        if script_settings.EnableResponses:
                            post("Queue successfully modified.")
                    else:
                        log_to_file("No changes were made to any redemptions.")
                except (ValueError, IndexError) as e:
                    if script_settings.EnableDebug:
                        log("Error encountered when editing redemption: " + e.message)
            else:
                log_to_file("Modification command did not have enough parameters. Displaying usage.")
                if script_settings.EnableResponses:
                    post("Usage: !" + script_settings.CommandName +
                         " edit <Index> <Username/Game/Message>:<Value>(|<Username/Game/Message>:<Value>|...)")


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
    log_to_file("Saving new settings from SL Chatbot GUI.")
    if script_settings.EnableDebug:
        log("Saving new settings from SL Chatbot GUI.")
    global event_receiver
    try:
        # Reload settings
        script_settings.__dict__ = json.loads(jsonData)
        script_settings.Save(SETTINGS_PATH)

        unload()
        start()
        log_to_file("Settings saved and applied successfully.")
        if script_settings.EnableDebug:
            log("Settings saved and applied successfully")
    except Exception as e:
        log_to_file("Error encountered when saving settings: " + str(e))
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
    log_to_file("Initializing receiver and connecting to Twitch channel")
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
    log_to_file("Connection result: " + str(result))
    if script_settings.EnableDebug: log("Connection result: " + str(result))
    user = json.loads(result["response"])
    user_id = user["data"][0]["id"]

    event_receiver.ListenToRewards(user_id)
    event_receiver.SendTopics(script_settings.TwitchOAuthToken)
    return


def event_receiver_reward_redeemed(sender, e):
    log_to_file("Channel point reward " + str(e.RewardTitle) + " has been redeemed with status " + str(e.Status) + ".")
    if script_settings.EnableDebug:
        log("Channel point reward " + str(e.RewardTitle) + " has been redeemed with status " + str(e.Status) + ".")

    if str(e.Status).lower() == "unfulfilled" and str(e.RewardTitle).lower() in \
            [name.strip().lower() for name in script_settings.TwitchRewardNames.split(",")]:
        log_to_file("Unfulfilled redemption matches a reward name. Starting thread to add the redemption.")
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
        log_to_file("Fulfilled redemption matches a reward name. "
                  "Attempting to auto-remove the redemption from the queue.")
        if script_settings.EnableDebug:
            log("Fulfilled redemption matches a reward name. Attempting to auto-remove the redemption from the queue.")
        for i in range(len(redemptions)):
            if redemptions[i].Username == e.DisplayName and redemptions[i].Message == e.Message:
                redemptions.pop(i)
                save_redemptions()
                log_to_file("Redemption at index " + str(i) + " automatically removed from the queue.")
                if script_settings.EnableDebug:
                    log("Redemption at index " + str(i) + " automatically removed from the queue.")
                return
        log_to_file("No matching redemption found. Was it already removed from the queue?")
        if script_settings.EnableDebug:
            log("No matching redemption found. Was it already removed from the queue?")
    else:
        log_to_file("Redemption is the wrong status and reward name. Skipping.")
        if script_settings.EnableDebug:
            log("Redemption is the wrong status and reward name. Skipping.")
    return


def reward_redeemed_worker(reward, message, data_username):
    log_to_file("Thread started. Processing " + reward + " redemption from " + data_username + " with message " + message)
    if script_settings.EnableDebug:
        log("Thread started. Processing " + reward + " redemption from " + data_username + " with message " + message)

    # When a person redeems, only a reward name and message is supplied. Attempt to detect which game is being redeemed
    # for by scanning the message for keywords
    new_game = "Unknown"
    detection_string = str(reward + ' ' + message).lower().strip().replace(" ", "").replace(":", "")
    game_information = {
        "Castlevania: SOTN Randomizer": {
            "keywords": [
                "Symphony of the Night",
                "SOTN",
                "empty hand",
                "empty-hand"
                "gem farmer",
                "gem-farmer"
                "scavenger",
                "adventure mode",
                "safe mode"],
            "likelihood": 0
        },
        "Chrono Trigger: Jets of Time Randomizer": {
            "keywords": [
                "Z1R",
                "Legend of Zelda Randomizer",
                "Zelda 1",
                "Zelda One",
                "Trigger",
                "Chrono",
                "Crono",
                "Ayla",
                "Marle",
                "Frog",
                "Lucca",
                "Robo",
                "Magus"
            ],
            "hits": 0
        },
        "Golden Sun: TLA Randomizer": {
            "keywords": [
                "TLA",
                "The Lost Age"
            ],
            "hits": 0
        },
        "FFIV: Free Enterprise": {
            "keywords": [
                "FE",
                "FF4 FE",
                "Free Enterprise",
                "FFIV",
                "FF4",
                "whichburn",
                "kmain",
                "ksummon",
                "kmoon",
                "ktrap",
                "spoon",
                "wincrystal",
                "afflicted",
                "battlescars",
                "bodyguard",
                "enemyunknown",
                "musical",
                "fistfight",
                "floorislava",
                "forwardisback",
                "friendlyfire",
                "gottagofast",
                "batman",
                "imaginarynumbers",
                "isthisrandomized",
                "kleptomania",
                "menarepigs",
                "biggermagnet",
                "mysteryjuice",
                "neatfreak",
                "omnidextrous",
                "payablegolbez",
                "bigchocobo",
                "sixleggedrace",
                "skywarriors",
                "worthfighting",
                "tellahmaneuver",
                "3point",
                "timeismoney",
                "unstackable",
                "noadamants"
            ],
            "hits": 0
        },
        "FFVI: Beyond Chaos": {
            "keywords": [
                "BC",
                "Beyond Chaos",
                "FFVI BC",
                "FF6 BC",
                "johnnydmad",
                "capslockoff",
                "alasdraco",
                "makeover",
                "notawaiter"
            ],
            "hits": 0
        },
        "FFVI: Worlds Collide": {
            "keywords": [
                "WC",
                "Worlds Collide",
                "FFVIWC",
                "FF6WC",
                "TimeForMemes",
                "Terra",
                "Relm",
                "Umaro",
                "Edgar",
                "Shadow",
                "Locke",
                "Sabin",
                "Strago",
                "Gau"
            ],
            "hits": 0
        },
        "Timespinner Randomizer": {
            "keywords": [
                "FFV",
                "FF5",
                "Career",
                "FFVCD",
                "FF5CD",
                "Final Fantasy 5",
                "Final Fantasy V",
                "Galuf",
                "Cara",
                "Faris",
                "Butz",
                "Lenna",
                "Krile"
            ],
            "hits": 0
        },
        "Secret of Mana Randomizer": {
            "keywords": [
                "Secret",
                "Mana",
                "SoM"
            ],
            "hits": 0
        },
        "SMRPG Randomizer": {
            "keywords": [
                "SMRPG",
                "Super",
                "Mario",
                "RPG",
                "Mallow",
                "Geno",
                "Cspjl",
                "fakeout"
            ],
            "hits": 0
        },
        "Streamer's Choice": {
            "keywords": [
                "Streamer",
                "Choice"
            ],
            "hits": 0
        },
        "Super Mario 3 Randomizer": {
            "keywords": [
                "Super Mario 3",
                "Mario 3",
                "SM3",
                "SM3R"
            ],
            "hits": 0
        },
        "Zelda 3: LTTP Randomizer": {
            "keywords": [
                "LTTP",
                "Link to the Past",
                "Pedestal",
                "Assured",
                "Z3R",
                "Zelda3"
            ],
            "hits": 0
        }
    }

    highest_hits = 0
    for game, game_data in game_information:
        if "keywords" in game_data:
            for keyword in game_data["keywords"]:
                if keyword.lower().strip().replace(" ", "").replace(":", "") in detection_string:
                    if "hits" in game_data:
                        log_to_file("Redemption matches keyword " + keyword + " under game " + game)
                        game_data["hits"] = game_data["hits"] + 1
                        if game_data["hits"] > highest_hits:
                            new_game = game
                            highest_hits = game_data["hits"]
                        elif game_data["hits"] == highest_hits:
                            new_game = new_game + " or " + game

    log_to_file("Redemption most closely matches game " + new_game + " with " + str(highest_hits) + " keyword hits.")

    # Create the new redemption object, append it to the list of redemptions, and save to file
    # (and Google Sheets, if enabled)
    new_redemption = Redemption(Username=data_username, Game=new_game, Message=message)
    redemptions.append(new_redemption)
    log_to_file("Saving new redemption.")
    save_redemptions()
    if script_settings.EnableResponses:
        post("Thank you for redeeming " + reward + ", " + data_username + ". Your game has been added to the queue.")
    
    global play_next_at
    play_next_at = datetime.datetime.now() + datetime.timedelta(0, 0)
    return


def unload():
    # Disconnect EventReceiver cleanly
    log_to_file("Redemption event listener being unloaded.")
    try:
        global event_receiver
        if event_receiver:
            event_receiver.Disconnect()
            log_to_file("Redemption event listener unloaded.")
            event_receiver = None
    except:
        log_to_file("Event receiver already disconnected")
    return


#   Opens readme file <Optional - DO NOT RENAME>
def openreadme():
    log_to_file("Opening readme file.")
    os.startfile(README_PATH)
    return


#   Opens Twitch.TV website to ask permissions
def get_token():
    log_to_file("Opening twitch web page to authenticate.")
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
            log_to_file("Redemptions.json did not exist. ")
            with io.open(REDEMPTIONS_PATH, 'w') as outfile:
                outfile.write(json.dumps({}))
                log_to_file("Redemptions.json has been created.")

        # record the redemptions
        log_to_file("Writing redemption objects to redemptions.json file.")
        with open (REDEMPTIONS_PATH, 'w') as outfile:
            outfile.seek(0)
            # When writing the Questions to disk, use the Question.toJSON() function
            json.dump(redemptions, outfile, indent=4, default=lambda q: q.toJSON())
            outfile.truncate()
            log_to_file("Redemption objects written to redemptions.json.")

        # Because of chatbot limitations, a secondary, external script is run to take the json file and upload
        # the redemption information to a Google Sheet. The settings file is shared between scripts.
        if script_settings.EnableGoogleSheets:
            # If the token json exists, check the expiry
            if script_settings.ExpiredTokenAction == "Chat Alert":
                if os.path.isfile(TOKEN_PATH):
                    with open(TOKEN_PATH, 'rb') as token_file:
                        token_json = json.loads(token_file.read().decode("utf-8-sig"))
                        if 'expiry' in token_json:
                            token_expiry = datetime.datetime.strptime(token_json['expiry'], "%Y-%m-%dT%H:%M:%S.%fZ")
                            if token_expiry < datetime.datetime.now():
                                post("Alert: Your Flag Tracker Google Sheets token is expired.")
                                return

            log_to_file("Google Sheets is enabled. Running GoogleSheetsUpdater.exe.")
            if script_settings.SpreadsheetID == "" or script_settings.Sheet == "":
                log("Error: You must enter a valid Spreadsheet ID and Sheet Name to use Google Sheets.")
                return
            threading.Thread(
                target=os.system,
                args=(GOOGLE_UPDATER_PATH,)
            ).start()
    except OSError as e:
        log("ERROR: Unable to save redemptions! " + e.message)


def load_redemptions():
    # Ensure the questions file exists
    log_to_file("Loading redemptions from redemptions.json.")
    if os.path.exists(REDEMPTIONS_PATH):
        log_to_file("Redemptions.json detected. Opening.")
        try:
            with open(REDEMPTIONS_PATH, "r") as infile:
                log_to_file("Loading object data from redemptions.json.")
                object_data = json.load(infile)    # Load the json data

                # For each object/question in the object_data, create new questions and feed them to the questions_list
                log_to_file("Creating redemption objects from the object data.")
                for redemption in object_data:
                    redemptions.append(
                        Redemption(
                            Username=redemption["Username"],
                            Game=redemption["Game"],
                            Message=redemption["Message"]
                        )
                    )
                log_to_file("Redemptions successfully loaded from redemptions.json")
                if script_settings.EnableDebug: log("Redemptions loaded: " + str(len(redemptions)))
        except Exception as e:
            log_to_file("ERROR loading redemptions from redemptions.json: " + str(e.message))
            if script_settings.EnableDebug: log("ERROR loading redemptions from redemptions.json: " + str(e.message))

    else:
        log_to_file("No redemptions file detected. Creating one.")
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


if __name__ == "__main__":
    args = raw_input("Enter the game name: ")
    somRegex = compile(r'[0-9a-fA-F]{50}')
    if any(re.search(keyword.lower(), args.lower()) for keyword in ["Secret\s?of\s?Mana", "\\bSoM\\b"]):
        newGame = "Secret of Mana Randomizer"
    elif search(somRegex, args):
        newGame = "Secret of Mana Randomizer"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["\\bBC\\b", "BeyondChaos", "FFVI\s?BC",
                                                                      "FF6\s?BC", "johnnydmad", "capslockoff",
                                                                      "alasdraco", "makeover" "notawaiter"]):
        newGame = "Beyond Chaos"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["\\bTS\\b", "Timespinner", "Lockbox", "Heirloom",
                                                                      "Fragile", "Talaria", "Stinky\s?Maw"]):
        newGame = "Timespinner Randomizer"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["\\bFFV\\b", "\\bFF5\\b", "Career\s?Day",
                                                                      "Career", "FFV\s?CD", "FF5\s?CD",
                                                                      "Final\s?Fantasy\s?5", "Final\s?Fantasy\s?V",
                                                                      "Galuf", "Cara", "Faris", "Butz", "Lenna",
                                                                      "Krile"]):
        newGame = "Career Day"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["SMRPG", "Super\s?Mario\s?RPG", "Geno", "Cspjl",
                                                                      "-fakeout"]):
        newGame = "SMRPG Randomizer"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["\\bWC\\b", "Worlds\s?Collide", "FFVI\s?WC",
                                                                      "FF6\s?WC", "Time\s?For\s?Memes", "Terra",
                                                                      "Relm", "Umaro", "Edgar", "Shadow", "Locke",
                                                                      "Sabin", "Strago", "Gau"]):
        newGame = "Worlds Collide"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["Super\s?Mario\s?3", "Mario\s?3", "\\bSM3\\b",
                                                                      "SM3R"]):
        newGame = "Super Mario 3 Randomizer"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["Symphony\s?of\s?the\s?Night", "SOTN",
                                                                      "empty-?hand", "gem-?farmer", "scavenger",
                                                                      "adventure\s?mode", "safe\s?mode"]):
        newGame = "SOTN Randomizer"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["LTTP", "Link\s?to\s?the\s?Past", "Swordless",
                                                                      "YAML", "Pedestal", "Retro", "Assured",
                                                                      "Shopsanity", "Berserker"]):
        newGame = "LTTP Randomizer"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["\\bFE\\b", "FF4\s?FE", "Free\s?Enterprise",
                                                                      "\\bFFIV\\b", "\\bFF4\\b", "whichburn",
                                                                      "kmain/summon/moon/trap", "spoon", "win:crystal",
                                                                      "afflicted", "battle\s?scars", "bodyguard",
                                                                      "enemy\s?unknown", "musical", "fist\s?fight",
                                                                      "floor\s?is\s?lava", "forward\s?is\s?back",
                                                                      "friendly\s?fire", "gotta\s?go\s?fast", "batman",
                                                                      "imaginary\s?numbers", "is\s?this\s?randomized",
                                                                      "kleptomania", "men\s?are\s?pigs",
                                                                      "bigger\s?magnet", "mystery\s?juice",
                                                                      "neat\s?freak", "omnidextrous",
                                                                      "payable\s?golbez", "big\s?chocobo",
                                                                      "six\s?legged\s?race", "sky\s?warriors",
                                                                      "worth\s?fighting", "tellah\s?maneuver", "3point",
                                                                      "time\s?is\s?money", "darts", "unstackable",
                                                                      "sylph", "no\s?adamants"]):
        newGame = "Free Enterprise"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["\\bJoT\\b", "CT\s?:?JoT", "Jets/s?of/s?Time",
                                                                      "Chrono\s?Trigger", "Crono\s?Trigger"]):
        newGame = "Jets of Time"
    elif any(re.search(keyword.lower(), args.lower()) for keyword in ["\\bpkmn\\b", "pokemon"]):
        newGame = "Pkmn KI Rando"
    else:
        newGame = "Unknown"

    print("Argument: " + args)
    print("Detected game: " + newGame)
