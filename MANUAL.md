# SC Wikelo Planner – Manual

## Quick guide

The Wikelo Planner shows which offers from **Wikelo's Emporium** you can fulfil with your resource stock and what you are still missing. You enter what you have on the left, and the offers on the right sort themselves accordingly.

### Areas

- **Header:** language **DE | EN**, **Light / Dark**, **🆕 What's new?**, **🔄 Load latest build (GitHub)** and **More tools**. The data line shows the patch, the data date and the number of offers.
- **View:** **By effort** or **By category**, your reputation under **My Wikelo reputation:**, the checkboxes **only reachable rep**, **show retired**, **show acquired** and the field **Filter offers…**.
- **Inventory:** **💾 Save stock**, **📂 Load stock** and **clear** (asks first).
- **My resource stock** (left): all ingredients, grouped by how you get them, e.g. Wikelo/Currency, Mining/Ore, Creature/Loot, Craftable (Blueprint). Plus the **Quick entry**, **Search resource…** and **show only "have"**.
- **Offers** (right): cards with all ingredients. Green chips you have, red ones are still missing (with "have/need").
- On a phone (narrow windows) you switch between the tabs **Offers** and **My inventory** at the top.

### Frequent actions

- Change an amount: **+** and **−** next to the ingredient. With Shift +10, with Ctrl +50, with Alt +100.
- The mouse wheel over an ingredient counts up or down, right-click subtracts.
- Clicking the name of an ingredient toggles between 0 and 1.
- Quick entry: `carinite 50` sets it to 50, `carinite +10` adds 10, just `carinite` adds 1. Choose with ↑↓, Enter applies.
- Clicking a red chip on a card adds 1 (more with Shift, Ctrl or Alt).
- **Get missing ▾** opens where the missing ingredients come from.
- **✓ acquired** hides an offer, **↩ undo** brings it back.

### Bands and effort

- In **By effort**, **Available now** is at the top, followed by **1 ingredient missing**, **2 ingredients missing**, **3+ ingredients missing**.
- The dots next to **Effort** (1 to 5) estimate how much work the missing items take: missing amount times the sourcing effort of the source.

### Data and storage

- Offers come from the community database [seeknd.github.io/Wikelo](https://seeknd.github.io/Wikelo/), blueprints and ore prices from [star-head.de](https://star-head.de). The data can change with every patch. Verify in game.
- **🔄 Load latest build (GitHub)** fetches the data built daily. Right-clicking it resets to the built-in data.
- Stock, "acquired" marks and settings stay only in this browser (localStorage). For a backup or another computer, use **💾 Save stock** (file `SC_Wikelo_Bestand.json`).
- Offline: download `SC_Wikelo_Planer.html` and open it with a double-click. It needs no internet.

## Tutorial: What can I get?

Goal: you enter your stock and find the offer that takes the least work.

1. In the **View** group, choose **By effort**.
2. Enter your Wikelo reputation under **My Wikelo reputation:**.
3. Tick **only reachable rep**. You then only see offers your reputation allows.
4. Click the **Quick entry** field on the left and type e.g. `carinite 50`. Press Enter. The ingredient is now at 50.
5. Enter all ingredients you have in game this way. For small amounts, **+** and **−** next to the ingredient are enough.
6. Tick **show only "have"**. The list now shows only what you entered. Use it to check the numbers.
7. Look at the **Available now** band on the right. You can collect these offers from Wikelo now.
8. If that band is empty, look at **1 ingredient missing**. Within a band, offers with little effort come first.
9. On a card, click **Get missing ▾**. For each missing ingredient you see its source and a hint, e.g. a blueprint recipe, a Wikelo exchange or an ore price.
10. Once you have collected an offer in game, click **✓ acquired** at the top of the card. The card disappears.
11. Click **💾 Save stock** so you have a backup as a file.

### Tips

- **Filter offers…** finds an offer quickly. The filter also searches the ingredients.
- **By category** sorts by Ship, Vehicle, Weapon, Armor, Gear and Unlock.
- A red badge **needs rep … ⚠** means the reputation you entered is not enough yet.
- **show acquired** brings hidden offers back. Next to it you see how many you have marked.

## Tutorial: Back up stock

Goal: you save your stock as a file and load it again on another computer or in another browser.

1. Enter your stock as described in the quick guide.
2. In the **Inventory** group, click **💾 Save stock**.
3. Depending on the browser, a save dialog opens, or the file `SC_Wikelo_Bestand.json` goes to your downloads.
4. To choose a different location, right-click **💾 Save stock**.
5. Copy the file to the other computer, e.g. via USB stick or a cloud folder.
6. Open the Wikelo Planner there and click **📂 Load stock**.
7. Choose the file `SC_Wikelo_Bestand.json`. A short "Stock loaded" message with the number of resources appears at the bottom.
8. Check the amounts on the left under **My resource stock**. Your "acquired" marks are back too.

### Tips

- Loading replaces the current stock and marks completely. Save first if you want to keep the old state.
- After you have loaded the file, clicking **💾 Save stock** writes straight back to that file in some browsers.
- **clear** only deletes the stock in the browser. The "acquired" marks stay.

## FAQ

### Why does an offer not match the game?

The offers come from a community database. Wikelo rotates offers, and patches change recipes. Click **🔄 Load latest build (GitHub)** and verify in game.

### Is my data gone if I switch browsers?

Yes. The stock is stored only in this browser's localStorage. Take it with you using **💾 Save stock** and **📂 Load stock**.

### What does "retired" mean?

The offer is no longer regularly available from Wikelo. **show retired** shows such offers. They carry a purple badge.

### How do I get the built-in data back?

Right-click **🔄 Load latest build (GitHub)** and confirm the question.
