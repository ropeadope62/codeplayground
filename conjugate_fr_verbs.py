#Quick conjugation of verbs into the correct form for je, tu, nous, il, elle, ils, elles, vous

print("Welcome to Dave's Python French Conjugator")
dictionary = {"je":"j'","tu":'es',"il ou elle":'e',"nous":
                  'ons',"vous":'ez',"ils ou elles":'ent'}

veb = input("What verb would you like to conjugate? \n")

for key in dictionary:
    if veb.endswith('er'):
        b = veb[:-2]
        if key == 'je':
            print(key, dictionary[key] + b + 'e')
        else:
            print(key,b + dictionary[key])