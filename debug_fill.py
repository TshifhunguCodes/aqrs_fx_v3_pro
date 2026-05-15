"""Test Telegram bot connectivity."""
from notifications import configure, send

configure("8969205648:AAF479_F3Ty3MMXy1J6629rIJZn775fWgeY", "8092229916")
result = send("🤖 <b>AQRS FX Pro V3</b>\n━━━━━━━━━━━━━━\nTest message from debug script", async_send=False)
print(f"Telegram test sent: {result}")