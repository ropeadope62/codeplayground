import random
    # simple game of hangman
    #word_list = ["aardvark", "baboon", "camel"]
from word_list import wordlist
from hangman_art import hangman_art
#Display the logo from the hangman_art module
game_started = True
while game_started == True: 
    print(f'''{hangman_art.logo}\n\n Welcome to Hangman!\n''')
    #Randomly choose a word from the word_list and assign it to a variable called chosen_word.
    word_list = wordlist.word_list
    chosen_word = random.choice(wordlist.word_list) 
    word_length = len(chosen_word)
    display = []
    for _ in range(word_length):
        display += '_'
    print(f'fyi {chosen_word} is the chosen word\n')
    lives_remaining = 6
    #Set the start of loop condition, in this case, a boolean for end of game
    end_of_game = False
    #while the game is not over
    while not end_of_game:
        print(f'{display}\n')
        #Ask the user to guess a letter and assign their answer to a variable called guess. Make guess lowercase.
        guess = input('Guess a letter...\n' ).lower()
        #A for loop to match the position of the guess if it is in the word and then add it to the display
        for position in range(word_length):
            letter = chosen_word[position]
            if letter == guess:
                print(f'Yes! {guess} is in the word!\n')
                display[position] = letter
        #Define the winning condition. We can assume the user has won the game when there are no blanks '_' remaining in display
        if '_' not in display:
            end_of_game = True
            print(display)
            print('You have won!\n')
            break
        # User chooses incorrectly, inform the user and lose a life. Also display the image of the new hangman stage
        if guess not in chosen_word:
            print(f'{guess} is not in the word. Try again.\n')
            #Print the hangman art based on how many lives they have remaining. Art is located in the hangman_art module
            print(f'''{hangman_art.stages[lives_remaining - 1]}''')
            lives_remaining -= 1 
            #If the user is out of lives, end the game by braking the whole not end_of_game loop
            if lives_remaining == 0:
                end_of_game = True
                print('You are out of lives. Game Over!')
    # If the user does not with to continue playing, end the game_started while loop by setting game_started = False
    play_another = input("Do you wish to play another game? 'yes' or 'no'\n").lower()
    if play_another == 'no':
        game_started = False 
        break
                
                
        
        #for letter in chosen_word:
        #    if letter == guess:
        #        print("Correct! You guessed right!")
        #        blanks = [letter for guess in chosen_word if letter == guess ]
        #        print(blanks)

        #       print("Wrong! You guessed Incorrectly!")
            


    #TODO-3 - Check if the letter the user guessed (guess) is one of the letters in the chosen_word.


