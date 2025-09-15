import discord
import requests
import imagehash
import re
from PIL import Image
from io import BytesIO
import os

#-------------------------CONFIG-------------------------
key_file = "CloudVisionKey.json"
key_path = os.path.join(os.path.dirname(__file__), key_file)
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
from google.cloud import vision

# BOT_TOKEN =
HASH_FILE = "blockedImages.txt"
SIMILARITY_THRESHOLD = 5

#-------------------------SETUP-------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

#-------------------------HELPER FUNCTIONS-------------------------
#Function to load saved image hashes
def load_hashes():
    try:
        with open(HASH_FILE, "r") as f:
            return {imagehash.hex_to_hash(line.strip()) for line in f if line.strip()}
    except FileNotFoundError:
        return set()

#Function to write image hashes to file
def save_hash(new_hash):
    with open(HASH_FILE, "a") as f:
        f.write(str(new_hash) + "\n")

#Function to check against blocked hashes
def check_blacklist(url, blocked_hashes):
   try:
       # Open url and save the hash of that image
       response = requests.get(url)
       img = Image.open(BytesIO(response.content))
       img_hash = imagehash.phash(img)

       # Compare the image hashes to every blocked hashes
       for blocked_hash in blocked_hashes:
           # If image hash is found then delete it
           print('difference', img_hash - blocked_hash)
           if img_hash - blocked_hash <= SIMILARITY_THRESHOLD:
               return True
       return False
   except Exception as e:
       print(e)
       return False

#Function to check image with ai
def check_img(url):
    print('checking image')
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image()
        image.source.image_uri = url

        response = client.web_detection(image=image)
        entities = response.web_detection.web_entities

        for entity in entities:
            print(entity.description.lower())
            if "nikocado avocado" in entity.description.lower() and entity.score > 0.8:
                img_response = requests.get(url)
                img_response.raise_for_status()
                img = Image.open(BytesIO(img_response.content))
                return imagehash.phash(img)
        print('nothing found')
        return None
    except Exception as e:
        print(e)
        return None

#-------------------------EVENTS AND COMMANDS-------------------------
#Function to show bot is ready
@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)

#Function to add blocked image and delete already blocked images
@client.event
async def on_message(message):
    #If message came from bot do nothing
    if message.author == client.user:
        return

    #If message was the block command
    if message.content.lower() == '!blockimage':
        #If message was a reply and original message has ID set originalMessage to that ID
        if message.reference and message.reference.message_id:
            original_message = await message.channel.fetch_message(message.reference.message_id)
            print(original_message.content)
            #If message has an attachment and is an image set the target to the first attachment
            if original_message.attachments and original_message.attachments[0].content_type.startswith("image/"):
                target = original_message.attachments[0]

                #Open the image url and save the hash of that image
                response = requests.get(target.url)
                img = Image.open(BytesIO(response.content))
                img_hash = imagehash.phash(img)

                #Load blocked hashes
                blocked_hashes = load_hashes()

                #If image isn't blocked add it to list
                if img_hash not in blocked_hashes:
                    save_hash(img_hash)
                    await message.channel.send("Image added to the ban list.")
                else:
                    await message.channel.send("Image already banned!.")
            #Else if the message is a url assign it to found_url
            if 'cdn.discordapp.com/attachments/' in original_message.content:
                found_urls = re.findall(r'https?://\S+', original_message.content)
                print('Found URL:', found_urls)

                #Parse the main url
                for url in found_urls:
                    main_url = url.split('?')[0]

                    #If mainUrl is an image check if its banned
                    if main_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        # Open the url and save the hash of that image
                        target = requests.get(url)
                        img = Image.open(BytesIO(target.content))
                        img_hash = imagehash.phash(img)

                        # Load blocked hashes
                        blocked_hashes = load_hashes()

                        # If image isn't blocked add it to list
                        if img_hash not in blocked_hashes:
                            save_hash(img_hash)
                            await message.channel.send("Image added to the ban list.")
                        else:
                            await message.channel.send("Image already banned!.")
            else:
                await message.channel.send("Image not found.")
        else:
            await message.channel.send("Reply to an image with !blockimage")
            return

    if message.attachments or re.search(r'https?://\S+', message.content):
        blocked_hashes = load_hashes()
        url = None

        # If message contains attachments
        if message.attachments:
            # Loop through attachments
            for attachment in message.attachments:
                # If attachment is an image
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    url = attachment.url
                    # If image matches blacklist
                    if check_blacklist(url, blocked_hashes):
                        await message.delete()
                        await message.channel.send("Stop sending banned images")
                        return
                    else:
                        ai_hash = check_img(url)
                        if ai_hash:
                            save_hash(ai_hash)
                            await message.delete()
                            await message.channel.send("Stop sending banned images")
                            return

        # If message has a url
        elif re.search(r'https?://\S+', message.content):
            #Loop through urls
            found_urls = re.findall(r'https?://\S+', message.content)
            for url in found_urls:
                main_url = url.split('?')[0]
                # If url is an image
                if main_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    # If image matches blacklist
                    if check_blacklist(url, blocked_hashes):
                        await message.delete()
                        await message.channel.send("Stop sending banned images")
                        return
                    else:
                        ai_hash = check_img(url)
                        if ai_hash:
                            save_hash(ai_hash)
                            await message.delete()
                            await message.channel.send("Stop sending banned images")
                            return

        #Safety case to do nothing is url is null
        elif url is None:
            return

#-------------------------RUN COMMAND-------------------------
client.run(BOT_TOKEN)