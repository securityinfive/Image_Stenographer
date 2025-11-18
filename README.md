# Image_Stenographer
Embed secret messages into image files and decode them.

This is a straight forward script to embed secret messaged into an image, called stenagraphy, and decode those images to get the message out. Not perfect, no error handling, but if you use straight text files or .msg files (text) it will work fine. 

You run this from a command line and can add manually typed text or from a text/message file. 

Usage:
To Encode: 

          - straight text 

         python image_message.py encode -i input.jpg -o output.png -m "secret msg" 
         
         - message in a text/msg file
         
         python image_message.py encode -i input.jpg -o output.png -t message.txt 

Decode: 

          - display the encoded output        
         
         python image_message.py decode -i output.png 
         
           - output encoded message to a file
         
         python image_message.py decode -i output.png > output_msg.txt 

It's best to save to a PNG file over a JPG.

Use this for your personal use and not to exfiltrate data in or out of protected environments...

The git_sample.png file has a message in it. 
