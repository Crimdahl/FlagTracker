# -*- coding: utf-8 -*-

# Importing Required Libraries
import sys
sys.platform = "win32"
import codecs, json, os, re, io, threading, datetime, clr, math, subprocess, inspect
clr.AddReference("IronPython.Modules.dll")
clr.AddReferenceToFileAndPath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "References", "TwitchLib.PubSub.dll"))
from TwitchLib.PubSub import TwitchPubSub

#   Script Information <Required>
ScriptName = "FlagTracker"
Website = "https://www.twitch.tv/Crimdahl"
Description = "Tracks User Flag Redemptions by writing to json file."
Creator = "Crimdahl"
Version = "1.2.0-Beta"

#   Define Global Variables <Required>
ScriptPath = os.path.dirname(__file__)
GoogleUpdaterPath = os.path.join(ScriptPath, "GoogleSheetsUpdater.exe")
SettingsPath = os.path.join(ScriptPath, "settings.json")
ReadmePath = os.path.join(ScriptPath, "Readme.md")
LogPath = os.path.join(ScriptPath, "flagtrackerlog.txt")
ScriptSettings = None
LogFile = None

Redemptions = []
RedemptionsPath = os.path.join(ScriptPath, "redemptions.json")

EventReceiver = None
ThreadQueue = []
Thread = None
PlayNextAt = datetime.datetime.now()

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
            self.SpreadsheetID = ""
            self.Sheet = ""

    def Reload(self, jsondata):
        self.__dict__ = json.loads(jsondata, encoding="utf-8")
        return

    def Save(self, SettingsPath):
        try:
            with codecs.open(SettingsPath, encoding="utf-8-sig", mode="w+") as f:
                json.dump(self.__dict__, f, encoding="utf-8")
        except:
            Log("Failed to save settings to the file. Fix error and try again")
        return

#   Process messages <Required>
def Execute(data):
    user_id = GetUserID(data.RawData)

    #Check if the streamer is live. Still run commands if the script is set to run while offline
    if Parent.IsLive() or not ScriptSettings.RunCommandsOnlyWhenLive:
        #Check if the message begins with "!" and the command name AND the user has permissions to run the command
        if (str(data.Message).startswith("!" + ScriptSettings.CommandName) and data.GetParamCount() == 1
            and (Parent.HasPermission(data.User, ScriptSettings.DisplayPermissions, "")                                                 
                or user_id == "216768170")):
            LogToFile("Base command received.")
            #If the user is using Google Sheets, post a link to the Google Sheet in chat
            if ScriptSettings.EnableGoogleSheets and ScriptSettings.SpreadsheetID != "":
                LogToFile("Displaying Google Sheets link in chat.")
                Post("https://docs.google.com/spreadsheets/d/" + ScriptSettings.SpreadsheetID)
                return
            #If the user is not using Google Sheets, read lines from the json file in the script directory
            else:
                LogToFile("Iterating through redemptions to display them in chat.")
                if len(Redemptions) > 0:
                    #An index is displayed with each line. The index can be referenced with other commands.
                    index = 1
                    for redemption in Redemptions:
                        Log(redemption.Game)
                        if ScriptSettings.DisplayMessageOnGameUnknown and redemption.Game == "Unknown":
                            Post(str(index) + ") " + redemption.Username + " - " + redemption.Message)
                        else:
                            Post(str(index) + ") " + redemption.Username + " - " + redemption.Game)
                        index = index + 1
                        if index > ScriptSettings.DisplayLimit:
                            break
                    return
                else:
                    Post("The community queue is empty!")
        #Check if the user is attempting to remove an item from the queue. Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + ScriptSettings.CommandName + " remove") 
            and (Parent.HasPermission(data.User, ScriptSettings.ModifyPermissions, "") 
                or user_id == "216768170")):
            LogToFile("Redemption removal command received.")
            #Check if the supplied information has three or more parameters: !command, remove, and one or more indices
            if data.GetParamCount() >= 3: 
                LogToFile("Attempting to remove the redemption(s)")
                DataString = str(data.Message)
                #Separate the indices from the rest of the message and split them by comma delimiter
                DataArray = DataString[DataString.index("remove") + len("remove"):].replace(" ","").split(",")
                #It is necessary to remove them from lowest index to highest index, so sort the indices first
                #Should I just remove from highest to lowest?
                DataArray.sort()
                if ScriptSettings.EnableDebug: Log("Removing the following indexes from Redemptions: " + str(DataArray))
                #Keep track of the number of indices removed because we have to subtract that number from the supplied indices
                RemovedCount = 1
                try:
                    for num in DataArray:
                        #The indices in the redemptions are 0-based, so we can immediately subtract 1 from any user-supplied indices
                        Redemptions.pop(int(num) - RemovedCount)
                        RemovedCount = RemovedCount + 1
                    SaveRedemptions()
                    LogToFile("Redemptions removed.")
                    if ScriptSettings.EnableResponses: Post("Redemption(s) successfully removed from the queue.")
                except (ValueError, IndexError) as e:
                    #Log an error if the index is either a non-integer or is outside of the range of the redemptions
                    if ScriptSettings.EnableDebug: Log("Error handled by remove: " + e.message)
                    if isinstance(e, IndexError):
                        if ScriptSettings.EnableResponses: Post("Error: Supplied index was out of range. The valid range is 1-" + str(len(Redemptions)) + ".")
            else:
                #If the supplied command is just "!<command_name> remove" and chat responses are enabled, display the command usage text in chat.
                LogToFile("Removal command did not have enough parameters. Displaying usage.")
                if ScriptSettings.EnableResponses: Post("Usage: !" + ScriptSettings.CommandName + " remove <Comma-Separated Integer Indexes>")
        #Check if the user is attempting to add an item to the queue. Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + ScriptSettings.CommandName + " add") 
            and (Parent.HasPermission(data.User, ScriptSettings.ModifyPermissions, "") 
                or user_id == "216768170")):
            LogToFile("Redemption addition command received.")
            #Check if the supplied information has three or more parameters: !command, add, and one or more sets of information
            if data.GetParamCount() >= 3: 
                LogToFile("Attempting to add redemption(s)")
                DataString = str(data.Message)
                #Separate the information sets from the rest of the message and split them by pipe delimiter
                DataArray = DataString[DataString.index("add") + len("add"):].split("|")
                redemptions_added = 0
                for info in DataArray:
                    if ScriptSettings.EnableDebug: Log("Adding new redemption via add command: " + str(info))
                    #Create a redemption object with the Username, Message, and Game
                    try:
                        #Username is mandatory
                        NewUser = GetAttribute("Username", info)
                        #Message is optional
                        NewMessage = "No message."
                        try:
                            NewMessage = GetAttribute("Message", info)
                        except (AttributeError, ValueError):
                            pass
                        #Game is optional
                        NewGame = "Unknown"
                        try:
                            NewGame = GetAttribute("Game", info)
                        except (AttributeError, ValueError):
                            pass

                        if "index:" in info:
                            Redemptions.insert(int(GetAttribute("Index", info)) - 1, Redemption(Username=NewUser, Message=NewMessage, Game=NewGame))
                            redemptions_added = redemptions_added + 1
                        else:        
                            Redemptions.append(Redemption(Username=NewUser, Message=NewMessage, Game=NewGame))
                            redemptions_added = redemptions_added + 1
                    except (AttributeError, ValueError) as e:
                        if ScriptSettings.EnableDebug: Log("Error handled by add: " + e.message)
                        continue
                #Save the new redemptions. This method also saves to Google Sheets if enabled, so no additional logic is required to 
                #   add entries to Google Sheets.
                if redemptions_added > 0:
                    SaveRedemptions()
                    LogToFile("Redemption(s) successfully added.")
                    if ScriptSettings.EnableResponses: Post("Successfully added " + str(redemptions_added) + " redemption(s) to the queue.")
                else:
                    LogToFile("ERROR: Failed to add redemption(s) to the queue.")
                    if ScriptSettings.EnableResponses: Post("Failed to add redemptions to the queue.")
            else:
                #If the supplied command is just "!<command_name> remove" and chat responses are enabled, display the command usage text in chat.
                LogToFile("Addition command did not have enough parameters. Displaying usage.")
                if ScriptSettings.EnableResponses: Post("Usage: !" + ScriptSettings.CommandName + " add Username:<UserName>, Message:<Message>, (Game:<Game>) | Username:<UserName>, ...")
        #Check if the user is attempting to edit an item in the queue. Uses different permissions from displaying the queue.
        elif (str.startswith(data.Message, "!" + ScriptSettings.CommandName + " edit") 
            and (Parent.HasPermission(data.User, ScriptSettings.ModifyPermissions, "") 
                or user_id == "216768170")):
            LogToFile("Redemption modification command received.")
            #This command takes 3 or more parameters: !<command_name>, an index, and attributes to edit at that index
            if data.GetParamCount() >= 3: 
                try:
                    changes = False
                    #Get the index and a set of comma-separated attributes from the message
                    index = int(data.GetParam(2))
                    Log("Index of edit:" + str(index))
                    data = str(data.Message)[len("!" + ScriptSettings.CommandName + " edit " + str(index)):].split(",")
                    Log("Data of edit:" + str(data))
                    target = Redemptions[index - 1]

                    #Attempt to modify each type of attribute. Do nothing if the attribute is not found. Save only if changes happen.
                    for attribute in data:
                        if "username" in attribute.lower():
                            try:
                                Log("Attempting to change username attribute.")
                                target.setUsername(GetAttribute("Username", attribute))
                                changes = True
                                Log("Username attribute changed.")
                            except (AttributeError, ValueError) as e:
                                if ScriptSettings.EnableDebug: Log("Error handled by edit: " + e.message)
                        if "message" in attribute.lower():
                            try:
                                Log("Attempting to change Message attribute.")
                                target.setMessage(GetAttribute("Message", attribute))
                                changes = True
                                Log("Message attribute changed.")
                            except (AttributeError, ValueError) as e:
                                if ScriptSettings.EnableDebug: Log("Error handled by edit: " + e.message)
                        if "game" in attribute.lower():
                            try:
                                Log("Attempting to change Game attribute.")
                                target.setGame(GetAttribute("Game", attribute))
                                changes = True
                                Log("Game attribute changed.")
                            except (AttributeError, ValueError) as e:
                                if ScriptSettings.EnableDebug: Log("Error handled by edit: " + e.message)
                    #Save the modified redemptions. This method also saves to Google Sheets if enabled, so no additional logic is required to 
                    #   modify entries in Google Sheets.
                    if changes: 
                        SaveRedemptions() 
                        LogToFile("Redemption(s) successfully modified.")
                        if ScriptSettings.EnableResponses: Post("Queue successfully modified.")
                    else:
                        LogToFile("No changes were made to any redemptions.")
                except (ValueError, IndexError) as e:
                    if ScriptSettings.EnableDebug: Log("Error handled by edit: " + e.message)
            else:
                LogToFile("Modification command did not have enough parameters. Displaying usage.")
                if ScriptSettings.EnableResponses: Post("Usage: !" + ScriptSettings.CommandName + " edit <Index> <Username/Game/Message>:<Value>")
    
#   [Required] Tick method (Gets called during every iteration even when there is no incoming data)
def Tick():
    global PlayNextAt
    if PlayNextAt > datetime.datetime.now():
        return

    global Thread
    if Thread and Thread.isAlive() == False:
        Thread = None

    if Thread == None and len(ThreadQueue) > 0:
        if ScriptSettings.EnableDebug: Log("Starting new thread. " + str(PlayNextAt))
        Thread = ThreadQueue.pop(0)
        Thread.start()

    return
    
#   Reload settings and receiver when clicking Save Settings in the Chatbot
def ReloadSettings(jsonData):
    LogToFile("Attempting to save settings.")
    if ScriptSettings.EnableDebug: Log("Saving settings.")
    global EventReceiver
    try:
        #Reload settings
        ScriptSettings.__dict__ = json.loads(jsonData)
        ScriptSettings.Save(SettingsPath)

        Unload()
        Start()
        LogToFile("Settings saved successfully.")
        if ScriptSettings.EnableDebug: Log("Settings saved successfully")
    except Exception as e:
        LogToFile("ERROR while saving settings: " + str(e.message))
        if ScriptSettings.EnableDebug: Log(str(e))
    return

#   Init called on script load. <Required>
def Init():
    #Initialize Settings
    global ScriptSettings
    LogToFile("\n\n")
    ScriptSettings = Settings(SettingsPath)
    ScriptSettings.Save(SettingsPath)
    
    #Initialize Redemption Receiver
    Start()
    LoadRedemptions()
    return

def Start():
    LogToFile("Starting channel point redemption receiver.")
    if ScriptSettings.EnableDebug: Log("Starting receiver")

    global EventReceiver
    EventReceiver = TwitchPubSub()
    EventReceiver.OnPubSubServiceConnected += EventReceiverConnected
    EventReceiver.OnRewardRedeemed += EventReceiverRewardRedeemed
    
    EventReceiver.Connect()
    return

def EventReceiverConnected(sender, e):
    LogToFile("Redemption event receiver connecting...")
    if ScriptSettings.EnableDebug: Log("Event receiver connecting")
    #  Get Channel ID for Username
    headers = {
        "Client-ID": "7a4xexuuxvxw5jmb9httrqq9926frq",
        "Authorization": "Bearer " + ScriptSettings.TwitchOAuthToken
    }
    result = json.loads(Parent.GetRequest("https://api.twitch.tv/helix/users?login=" + Parent.GetChannelName(), headers))
    LogToFile("Result of connection attempt: " + str(result))
    if ScriptSettings.EnableDebug: Log("result: " + str(result))
    user = json.loads(result["response"])
    id = user["data"][0]["id"]

    LogToFile("Event receiver connected, sending topics for channel id: " + id)
    if ScriptSettings.EnableDebug: Log("Event receiver connected, sending topics for channel id: " + id)

    EventReceiver.ListenToRewards(id)
    EventReceiver.SendTopics(ScriptSettings.TwitchOAuthToken)
    return

def EventReceiverRewardRedeemed(sender, e):
    LogToFile("Redemption event triggered.")
    if ScriptSettings.EnableDebug: Log("Event triggered")

    dataUser = e.Login
    dataUserName = e.DisplayName
    reward = e.RewardTitle
    message = e.Message

    LogToFile("Redeemed reward title:" + str(e.RewardTitle.lower()))
    Log("Redeemed reward title:" + str(e.RewardTitle.lower()))
    #Log("Rewards in settings:" + str([name.strip().lower() for name in ScriptSettings.TwitchRewardNames.split(",")]))
    
    LogToFile("Starting thread to handle the redemption.")
    if e.RewardTitle.lower() in [name.strip().lower() for name in ScriptSettings.TwitchRewardNames.split(",")]:
        ThreadQueue.append(threading.Thread(target=RewardRedeemedWorker,args=(reward, message, dataUser, dataUserName)))
    return

def RewardRedeemedWorker(reward, message, dataUser, dataUserName):
    if ScriptSettings.EnableDebug:
        Log(dataUserName + " is redeeming " + reward + " with flag information " + message)

    #When a person redeems, only a reward name and message is supplied. Attempt to detect which game is being redeemed for by scanning the message for keywords
    MessageString = str(message)
    if any (keyword in MessageString for keyword in ["FF4FE", "Free Enterprise", "FFIV", "FF4", "whichburn", "kmain/summon/moon/trap", "spoon", "win:crystal"]):
        New_Game = "FF4 Free Enterprise"
    elif any (keyword in MessageString for keyword in ["WC", "Worlds Collide", "FFVIWC", "FF6WC"]) or len(MessageString) > 350:
        New_Game = "FF6 Worlds Collide"
    elif any (keyword in MessageString for keyword in ["BC", "Beyond Chaos", "FFVIBC", "FF6BC", "johnnydmad", "capslockoff", "alasdraco", "makeover" "notawaiter"]):
        New_Game = "FF6 Beyond Chaos"
    elif any (keyword in MessageString for keyword in ["TS", "Timespinner", "Lockbox", "Heirloom", "Fragile", "Talaria"]):
        New_Game = "Timespinner"
    elif any (keyword in MessageString for keyword in ["FFV", "Career", "FFVCD"]):
        New_Game = "FF5 Career Day"
    elif any (keyword in MessageString for keyword in ["SMRPG", "Super Mario RPG", "Geno", "Cspjl", "-fakeout"]):
        New_Game = "SMRPG Randomizer"
    elif any (keyword in MessageString for keyword in ["Secret of Mana", "SoM"]):
        New_Game = "Secret of Mana Randomizer"
    elif any (keyword in MessageString for keyword in ["Super Mario 3", "Mario 3", "SM3", "SM3R"]):
        New_Game = "Super Mario 3 Randomizer"
    else:
        New_Game = "Unknown"

    #Create the new redemption object, append it to the list of redemptions, and save to file (and Google Sheets, if enabled)
    LogToFile("Creating new redemption object.")
    new_redemption = Redemption(Username=dataUserName, Game=New_Game, Message=message)
    LogToFile("Object created. Appending object to redemptions list.")
    Redemptions.append(new_redemption)
    LogToFile("Saving redemptions.")
    SaveRedemptions()
    if ScriptSettings.EnableResponses: Post("Thank you for redeeming " + reward + ", " + dataUserName + ". Your game has been added to the queue.")
    
    global PlayNextAt
    PlayNextAt = datetime.datetime.now() + datetime.timedelta(0, 0)
    return

def Unload():
    # Disconnect EventReceiver cleanly
    LogToFile("Redemption event listener being unloaded.")
    try:
        global EventReceiver
        if EventReceiver:
            EventReceiver.Disconnect()
            LogToFile("Redemption event listener unloaded.")
            EventReceiver = None
    except:
        if ScriptSettings.EnableDebug: Log("Event receiver already disconnected")

    return

#   Opens readme file <Optional - DO NOT RENAME>
def openreadme():
    LogToFile("Opening readme file.")
    os.startfile(ReadmePath)
    return

#   Opens Twitch.TV website to ask permissions
def GetToken(): 
    LogToFile("Opening twitch web page to authenticate.")
    os.startfile("https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=7a4xexuuxvxw5jmb9httrqq9926frq&redirect_uri=https://twitchapps.com/tokengen/&scope=channel:read:redemptions&force_verify=true")
    return

#   Helper method to log
def Log(message): 
    Parent.Log(ScriptName, message)

def LogToFile(line):
    global LogFile
    LogFile = open(LogPath, "a+")
    LogFile.writelines(str(datetime.datetime.now()) + " " + line + "\n")
    LogFile.close()

#   Helper method to post to Twitch Chat
def Post(message):
    Parent.SendStreamMessage(message)

def SaveRedemptions():
    try:        
        #if the redemptions file does not exist, create it
        if not os.path.exists(RedemptionsPath):
            LogToFile("Redemptions.json did not exist. ")
            with io.open(RedemptionsPath, 'w') as outfile:
                outfile.write(json.dumps({}))
                LogToFile("Redemptions.json has been created.")

        #record the redemptions
        LogToFile("Writing redemption objects to redemptions.json file.")
        with open (RedemptionsPath, 'w') as outfile:
            outfile.seek(0)
            #When writing the Questions to disk, use the Question.toJSON() function
            json.dump(Redemptions, outfile, indent=4, default=lambda q: q.toJSON())
            outfile.truncate()
            LogToFile("Redemption objects written to redemptions.json.")

        #Because of chatbot limitations, a secondary, external script is run to take the json file and upload
        #   the redemption information to a Google Sheet. The settings file is shared between scripts.
        if ScriptSettings.EnableGoogleSheets: 
            LogToFile("Google Sheets is enabled. Running GoogleSheetsUpdater.exe.")
            if ScriptSettings.SpreadsheetID == "" or ScriptSettings.Sheet == "":
                Log("Error: You must enter a valid Spreadsheet ID and Sheet Name to use Google Sheets.")
                return
            os.system(GoogleUpdaterPath)
    except OSError as e:
        Log("ERROR: Unable to save redemptions! " + e.message)

def LoadRedemptions():
    #Ensure the questions file exists
    LogToFile("Loading redemptions from redemptions.json.")
    if os.path.exists(RedemptionsPath):
        LogToFile("Redemptions.json detected. Opening.")
        try:
            with open(RedemptionsPath, "r") as infile:
                LogToFile("Loading object data from redemptions.json.")
                objectdata = json.load(infile)    #Load the json data

                #For each object/question in the objectdata, create new questions and feed them to the questions_list
                LogToFile("Creating redemption objects from the object data.")
                for redemption in objectdata:
                    Redemptions.append(Redemption(Username=redemption["Username"], Game=redemption["Game"], Message=redemption["Message"]))
                LogToFile("Redemptions successfully loaded from redemptions.json")
                if ScriptSettings.EnableDebug: Log("Redemptions loaded: " + str(len(Redemptions)))
        except Exception as e:
            LogToFile("ERROR loading redemptions from redemptions.json: " + str(e.message))
            if ScriptSettings.EnableDebug: Log("ERROR loading redemptions from redemptions.json: " + str(e.message))

    else:
        LogToFile("No redemptions file detected. Creating one.")
        if ScriptSettings.EnableDebug: Log("WARNING: No redemptions file exists. Creating one.")
        open(RedemptionsPath, "w").close

def GetAttribute(attribute, message):
    attribute = attribute.lower() + ":"
    #The start index of the attribute begins at the end of the attribute designator, such as "game:"
    try:
        index_of_beginning_of_attribute = message.lower().index(attribute) + len(attribute)
    except ValueError as e:
        raise e
    #The end index of the attribute is at the last space before the next attribute designator, or at the end of the message
    try:
        index_of_end_of_attribute = message[index_of_beginning_of_attribute:index_of_beginning_of_attribute + message[index_of_beginning_of_attribute:].index(":")].rindex(",")
    except ValueError:
        #If this error is thrown, the end of the message was hit, so just return all of the remaining message
        return message[index_of_beginning_of_attribute:].strip()
    return message[index_of_beginning_of_attribute:index_of_beginning_of_attribute + index_of_end_of_attribute].strip().strip(",")

def GetUserID(rawdata):
    #Retrieves the user ID of a Twitch chatter using the raw data returned from Twitch
    try:
        rawdata = rawdata[rawdata.index("user-id=") + len("user-id="):]
        rawdata = rawdata[:rawdata.index(";")]
    except Exception:
        return ""
    return rawdata