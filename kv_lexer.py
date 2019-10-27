# Reads QPC files and returns a list of QPCBlocks

import os


class KeyValue:
    def __init__(self, file_path, line_num, key, value):
        self.key = key
        self.value = value
        # self.condition = condition
        self.items = []
        self.line_num = line_num
        self.file_path = file_path
    
    def InvalidOption(self, *valid_option_list):
        print( "WARNING: Invalid Option" )
        print( "\tValid Options:\n\t\t" + '\n\t\t'.join(valid_option_list) )
        self.PrintInfo()
    
    # would be cool if i could change the colors on this
    def FatalError(self, message):
        print("FATAL ERROR: " + message)
        self.PrintInfo()
        quit()
    
    # should Error and FatalError be the same?
    def Error(self, message):
        print("ERROR: " + message)
        self.PrintInfo()
    
    def Warning(self, message):
        print("WARNING: " + message)
        self.PrintInfo()
    
    def PrintInfo(self):
        # TODO: this path is relative to the current directory
        print("\tFile Path: " + self.file_path +
              "\n\tLine: " + str(self.line_num) +
              "\n\tKey: " + self.key +
              "\n\tValue: " + self.value)
        # maybe check the type of value so it only prints if it's a string?
        
        
def ReadFile(path):
    lexer = KeyValuesLexer(path)
    qpc_file = []
    path = os.getcwd() + os.sep + path

    while lexer.chari < lexer.file_len:
        key, line_num = lexer.NextKey()
        
        if not key:
            break  # end of file
        
        values = lexer.NextValue()
        # condition = lexer.NextCondition()
        
        block = KeyValue(path, line_num, key, values)
        
        if lexer.NextSymbol() == "{":
            CreateSubBlock(lexer, block, path)
            pass
        
        qpc_file.append(block)
    
    return qpc_file


def CreateSubBlock(lexer, block, path):
    while lexer.chari < lexer.file_len - 1:
        key, line_num = lexer.NextKey()
        
        if not key:
            if lexer.NextSymbol() == "}":
                return
            print( "uhhhhhhh" )
        
        # line_num = lexer.linei
        value = lexer.NextValue()
        # condition = lexer.NextCondition()

        sub_block = KeyValue(path, line_num, key, value)

        block.items.append(sub_block)
    
        next_symbol = lexer.NextSymbol()
        if next_symbol == "{":
            CreateSubBlock(lexer, sub_block, path)
        elif next_symbol == "}":
            return
        
    
class KeyValuesLexer:
    def __init__(self, path):
        self.chari = 0
        self.linei = 1
        self.path = path
        
        with open(path, mode="r", encoding="utf-8") as file:
            self.file = file.read()
        self.file_len = len(self.file) - 1
        
        # maybe using this would be faster?
        self.keep_from = 0

        self.chars_comment = {'/', '*'}
        self.chars_escape = {'"', '\'', '\\'}
        self.chars_quote = {'"', '\''}
        self.chars_cond = {'[', ']'}
        self.chars_item = {'{', '}'}
        
    def NextValue(self):
        value = ''
        while self.chari < self.file_len:
            char = self.file[self.chari]

            if char in self.chars_item:
                break
                
            if char in {' ', '\t'}:
                self.chari += 1
                if value:
                    break
                continue
    
            if char in self.chars_quote:
                value = self.ReadQuote(char)
                break
    
            # skip escape
            if char == '\\' and self.NextChar() in self.chars_escape:
                self.chari += 2
                value += self.file[self.chari]
    
            # TODO: replace "items" with just value, so this will need to be changed
            elif char == '\n':
                break

            elif char == '/' and self.NextChar() in self.chars_comment:
                self.SkipComment()
    
            else:
                if self.file[self.chari] in self.chars_cond:
                    break
                value += self.file[self.chari]
    
            self.chari += 1
        
        return value

    def NextChar(self):
        if self.chari + 1 >= self.file_len:
            return None
        return self.file[self.chari + 1]

    # used to be NextString, but i only used it for keys
    def NextKey(self):
        string = ''
        line_num = 0
        skip_list = {' ', '\t', '\n'}
        
        while self.chari < self.file_len:
            char = self.file[self.chari]
            
            if char in self.chars_item:
                line_num = self.linei
                break

            elif char in {' ', '\t'}:
                if string:
                    line_num = self.linei
                    break

            elif char in self.chars_quote:
                string = self.ReadQuote(char)
                line_num = self.linei
                break
            
            # skip escape
            elif char == '\\' and self.NextChar() in self.chars_escape:
                self.chari += 2
                string += self.file[self.chari]
                # char = self.file[self.chari]
            
            elif char in skip_list:
                if string:
                    # self.chari += 1
                    line_num = self.linei
                    # if char == '\n':
                    #     self.linei += 1
                    break
                if char == '\n':
                    self.linei += 1
                
            elif char == '/' and self.NextChar() in self.chars_comment:
                self.SkipComment()
                
            else:
                string += self.file[self.chari]

            self.chari += 1
            
        return string, line_num

    def NextSymbol(self):
        while self.chari < self.file_len:
            char = self.file[self.chari]

            if char in self.chars_item:
                self.chari += 1
                return char
            
            # skip escape
            elif char == '\\' and self.NextChar() in self.chars_escape:
                self.chari += 2
            
            elif char == '/' and self.NextChar() in self.chars_comment:
                self.SkipComment()
                
            elif char == '\n':
                self.linei += 1
                
            elif char not in {' ', '\t'}:
                break

            self.chari += 1
            
        return None

    def NextCondition(self):
        condition = ''
        in_cond = False
        while self.chari < self.file_len:
            char = self.file[self.chari]
        
            if char in self.chars_item:
                break
        
            elif char == '[':
                self.chari += 1
                in_cond = True
                continue
        
            elif char == ']':
                self.chari += 1
                in_cond = False
                break
        
            elif char in {' ', '\t'}:
                self.chari += 1
                continue
        
            elif char == '\n':
                # self.linei += 1
                # self.chari += 1
                break
        
            elif char == '/' and self.NextChar() in self.chars_comment:
                self.SkipComment()
        
            elif in_cond:
                condition += self.file[self.chari]
                
            else:
                break
        
            self.chari += 1
            
        return condition
    
    def SkipComment(self):
        self.chari += 1
        char = self.file[self.chari]
        if char == '/':
            # keep going until \n
            while True:
                self.chari += 1
                if self.file[self.chari] == "\n":
                    self.linei += 1
                    break
    
        elif char == '*':
            while True:
                char = self.file[self.chari]
            
                if char == '*' and self.NextChar() == '/':
                    self.chari += 1
                    break
            
                if char == "\n":
                    self.linei += 1
            
                self.chari += 1

    def ReadQuote(self, qchar):
        quote = ''
    
        while self.chari < self.file_len:
            self.chari += 1
            char = self.file[self.chari]
        
            if char == '\\' and self.NextChar() in self.chars_escape:
                quote += self.NextChar()
                self.chari += 1
            elif char == qchar:
                break
            else:
                quote += char
    
        self.chari += 1
        return quote

