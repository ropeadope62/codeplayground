#Blackjack simple single deck counter 
#Version 0.1
#Author: ropeadope62
#Git: https://github.com/ropeadope62
print("""
                 /######/\/
               /##########\/
              /   \###/    \/
             /     \#/      \/
          /\|               |/\/
          | | \ ==\    /== / | |
           \|  \<|>\  /<|>/  |/     /|
    \__     |    -   \  -    |     /#|
     \#\     |        |      |   /###|
      \##\   |       \|     |  /#####|
       \###\  |   _______  | /######|
        \####\ | / \/ \/ \|/#######|
        |######\|        |#########|
        |########\______/##########|
        |#########\    /##########/
        |##########\  |#########/\/
        /###########\/########/###\/
    /################\######/########\/
   /##################\###/###########\/
  /###################\#/##############\/
 /###### THE COUNT VON COUNTER #########\/
/###################/####################\/ \n
""")
printascii(vamp)
print("Another stupid app made by ropeadope62 ")
cards_total = 52
running_count = 0
already_counted = []
card_vals = {"2": 1 , "3": 1, "4": 1, "5":1, "6": 1, "7": 0, "8": 0, "9": 0,
"10": -1, "J": -1, "Q": -1 , "K":-1, "A": -1}

def countcard(card):
    global cards_total
    cards_total -= 1
    for key, value in card_vals.items():
        if card in key:
            already_counted.append(key)
            global running_count
            running_count += value
        elif card == "R":
            cards_total = 52
            running_count = 0
            already_counted.clear()

print(f"Welcome to The Count Von Count Counter\n At any point, enter 'R' instead of the card played to reset the count.")

while cards_total > 0:
    card = input(f"Enter the dealt cards one by one. Possible cards: 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A\n CURRENT RUNNING COUNT: {running_count}\n CARDS REMAINING IN DECK: {cards_total}\n PREVIOUS 5 CARDS: {already_counted[-5:]}\n ")
    countcard(card)
