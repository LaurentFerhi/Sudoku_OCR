import numpy as np
from collections import Counter

def valid_list(l):
    
    c = Counter(l)
    c.pop(0)
    if any(v != 1 for v in c.values()):
        return False
    return True

def check_solvability(grid):
    
    # check rows
    for row in grid:
        if not valid_list(row):
            return False

    # check cols
    t_grid = grid.transpose()
    for row in t_grid:
        if not valid_list(row):
            return False
    
    #check boxes
    for i in range(0,9,3):
        for j in range(0,9,3):
            l = np.array([list(col[j:j+3]) for col in grid[i:i+3]]).flatten()
            if not valid_list(l):
                return False
            
    return True

def print_board(grid):
    
    for row in range(len(grid)):
        if row%3 == 0 and row!=0:
            print(11*"- ")

        for col in range(len(grid[0])):
            if col%3 == 0 and col!=0:
                print("| ", end="")

            if col == 8:
                print(grid[row][col])
            elif grid[row][col] == 0:
                print("0 ", end="")
            else:
                print(str(grid[row][col]) + " ", end="")

def find_empty(grid):
    
    # i = row, j = col
    for i in range(len(grid)):
        for j in range(len(grid[0])):
            if grid[i][j] == 0:
                return (i, j)
    return None

def valid(grid, num, position=tuple):
    
    # Check row
    for i in range(len(grid[0])):
        if grid[position[0]][i] == num and position[1] != i:
            return False

    # Check col
    for i in range(len(grid)):
        if grid[i][position[1]] == num and position[0] != i:
            return False

    # Check box
    box_x = position[1] // 3
    box_y = position[0] // 3

    for i in range(box_y*3, box_y*3 + 3):
        for j in range(box_x * 3, box_x*3 + 3):
            if grid[i][j] == num and (i,j) != position:
                return False

    return True

def solve(grid):
    
    find = find_empty(grid)
    if not find:
        return True
    else:
        row, col = find

    for i in range(1,10):
        if valid(grid, i, (row, col)):
            grid[row][col] = i

            if solve(grid):
                return True
            else:
                # if position not valid, rewrite 0
                grid[row][col] = 0

    return False
