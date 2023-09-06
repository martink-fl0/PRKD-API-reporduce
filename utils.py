def convert_score_to_int(score):
    if '+' in str(score):
        return int(str(score)[1:])
    elif score == 'E':
        return 0
    else:
        return int(score)
    
def convert_int_to_score(num):
    if num > 0:
        return '+' + str(num)
    elif num == 0:
        return 'E'
    else:
        return str(num)