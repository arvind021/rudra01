# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


from pyrogram import Client

from anony import config, logger


class Userbot:
    def __init__(self):
        """
        Initializes the userbot with multiple clients.

        This method sets up clients for the userbot using predefined session strings.
        Each client is assigned a unique name based on the key in the `clients` dictionary.
        """
        self.clients = []
        
        # ✅ FIX: Dynamic clients based on available sessions
        self.sessions = {}
        
        if hasattr(config, 'SESSION1') and config.SESSION1:
            self.sessions['one'] = 'SESSION1'
        if hasattr(config, 'SESSION2') and config.SESSION2:
            self.sessions['two'] = 'SESSION2'
        if hasattr(config, 'SESSION3') and config.SESSION3:
            self.sessions['three'] = 'SESSION3'
        
        # ✅ FIX: अगर कोई SESSION नहीं है तो default SESSION use करो
        if not self.sessions and hasattr(config, 'SESSION') and config.SESSION:
            self.sessions['one'] = 'SESSION'
        
        # ✅ Create clients dynamically
        for idx, (key, string_key) in enumerate(self.sessions.items(), 1):
            name = f"AnonyUB{idx}"
            session_string = getattr(config, string_key, None)
            
            if not session_string:
                logger.warning(f"No session string found for {string_key}")
                continue
            
            try:
                client = Client(
                    name=name,
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    session_string=session_string,
                )
                setattr(self, key, client)
            except Exception as e:
                logger.error(f"Failed to create client {name}: {e}")

    async def boot_client(self, num: int, key: str):
        """
        Boot a client and perform initial setup.
        Args:
            num (int): The client number to boot (1, 2, or 3).
            key (str): The client key (one, two, three).
        Raises:
            SystemExit: If the client fails to send a message in the log group.
        """
        try:
            client = getattr(self, key, None)
            if not client:
                logger.warning(f"Client {key} not found")
                return
            
            await client.start()
            
            # ✅ Log message भेजो
            try:
                await client.send_message(config.LOGGER_ID, "🤖 Assistant Started")
            except Exception as e:
                logger.warning(f"Assistant {num} failed to send message in log group: {e}")

            # ✅ Client info set करो
            me = await client.get_me()
            client.id = me.id
            client.name = me.first_name
            client.username = me.username
            client.mention = me.mention
            self.clients.append(client)
            
            logger.info(f"✅ Assistant {num} started as @{client.username}")
            
        except Exception as e:
            logger.error(f"Failed to boot Assistant {num}: {e}")

    async def boot(self):
        """
        Asynchronously starts the assistants.
        """
        if not self.sessions:
            logger.warning("⚠️ No sessions configured. Using bot without assistants.")
            return
        
        for idx, (key, string_key) in enumerate(self.sessions.items(), 1):
            await self.boot_client(idx, key)

    async def exit(self):
        """
        Asynchronously stops the assistants.
        """
        for client in self.clients:
            try:
                await client.stop()
            except:
                pass
        logger.info("✅ Assistants stopped.")
