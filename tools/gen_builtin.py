#!/usr/bin/env python3
"""Translate gojq's generated builtin.go (Go composite literals of the AST of
builtin.jq) into src/gojq/builtin.hd, the same data as hd constructors."""
import re, sys

FIELDS = {  # struct -> field -> (hd name, kind, type)
 'FuncDef': {'Name': ('name','str',None), 'Args': ('args','strs',None), 'Body': ('body','req','Query')},
 'Query': {'FuncDefs': ('func_defs','list','FuncDef'), 'Term': ('term','opt','Term'), 'Left': ('left','opt','Query'),
           'Right': ('right','opt','Query'), 'Patterns': ('patterns','list','Pattern'), 'Op': ('op','enum',None)},
 'Term': {'Type': ('typ','enum',None), 'Index': ('index','opt','Index'), 'Func': ('func','opt','Func'),
          'Object': ('object','opt','Object'), 'Array': ('array','opt','Array'), 'Number': ('number','str',None),
          'Unary': ('unary','opt','Unary'), 'Format': ('format','str',None), 'Str': ('str','opt','String'),
          'If': ('if_','opt','If'), 'Try': ('try_','opt','Try'), 'Reduce': ('reduce','opt','Reduce'),
          'Foreach': ('foreach','opt','Foreach'), 'Label': ('label','opt','Label'), 'Break': ('break_','str',None),
          'Query': ('query','opt','Query'), 'SuffixList': ('suffix_list','list','Suffix')},
 'Index': {'Name': ('name','str',None), 'Str': ('str','opt','String'), 'Start': ('start','opt','Query'),
           'End': ('end','opt','Query'), 'IsSlice': ('is_slice','bool',None)},
 'Func': {'Name': ('name','str',None), 'Args': ('args','list','Query')},
 'String': {'Str': ('str','str',None), 'Queries': ('queries','optlist','Query')},
 'Object': {'KeyVals': ('key_vals','list','ObjectKeyVal')},
 'ObjectKeyVal': {'Key': ('key','str',None), 'KeyString': ('key_string','opt','String'),
                  'KeyQuery': ('key_query','opt','Query'), 'Val': ('val','opt','Query')},
 'Array': {'Query': ('query','opt','Query')},
 'Suffix': {'Index': ('index','opt','Index'), 'Iter': ('iter','bool',None), 'Optional': ('optional','bool',None)},
 'If': {'Cond': ('cond','req','Query'), 'Then': ('then_','req','Query'), 'Elif': ('elif','list','IfElif'), 'Else': ('else_','opt','Query')},
 'IfElif': {'Cond': ('cond','req','Query'), 'Then': ('then_','req','Query')},
 'Try': {'Body': ('body','req','Query'), 'Catch': ('catch','opt','Query')},
 'Reduce': {'Query': ('query','req','Query'), 'Patterns': ('patterns','list','Pattern'), 'Start': ('start','req','Query'), 'Update': ('update','req','Query')},
 'Foreach': {'Query': ('query','req','Query'), 'Patterns': ('patterns','list','Pattern'), 'Start': ('start','req','Query'),
             'Update': ('update','req','Query'), 'Extract': ('extract','opt','Query')},
 'Unary': {'Op': ('op','enum',None), 'Term': ('term','req','Term')},
 'Pattern': {'Name': ('name','str',None), 'Array': ('array','list','Pattern'), 'Object': ('object','list','PatternObject')},
 'PatternObject': {'Key': ('key','str',None), 'KeyString': ('key_string','opt','String'), 'KeyQuery': ('key_query','opt','Query'), 'Val': ('val','opt','Pattern')},
 'Label': {'Ident': ('ident','str',None), 'Body': ('body','req','Query')},
}
HDNAME = {'String': 'StringT'}

class P:
    def __init__(self, s): self.s, self.i = s, 0
    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in ' \t\n': self.i += 1
    def peek(self, t): self.ws(); return self.s.startswith(t, self.i)
    def eat(self, t):
        self.ws()
        assert self.s.startswith(t, self.i), (t, self.s[self.i:self.i+60]); self.i += len(t)
    def ident(self):
        self.ws(); m = re.compile(r'[A-Za-z_][A-Za-z0-9_]*').match(self.s, self.i); self.i = m.end(); return m.group(0)
    def gostring(self):
        self.ws(); assert self.s[self.i] == '"'; j = self.i + 1; out = ''
        while self.s[j] != '"':
            if self.s[j] == '\\':
                out += {'n':'\n','t':'\t','"':'"','\\':'\\','r':'\r'}[self.s[j+1]]; j += 2
            else: out += self.s[j]; j += 1
        self.i = j + 1; return out

def hdstr(s):
    return '"' + s.replace('\\','\\\\').replace('"','\\"').replace('$','\\$').replace('\n','\\n').replace('\t','\\t').replace('\r','\\r') + '"'

def struct_body(p, typ):
    """`{ Field: value, ... }` of struct typ -> hd constructor text."""
    p.eat('{'); parts = []
    while not p.peek('}'):
        f = p.ident(); p.eat(':')
        name, kind, sub = FIELDS[typ][f]
        if kind == 'str': v = hdstr(p.gostring())
        elif kind == 'bool': v = p.ident()
        elif kind == 'enum': v = '.' + p.ident()
        elif kind == 'strs':
            p.eat('[]string{'); xs = []
            while not p.peek('}'):
                xs.append(hdstr(p.gostring()))
                if p.peek(','): p.eat(',')
            p.eat('}'); v = '[' + ', '.join(xs) + ']'
        elif kind in ('req', 'opt'):
            p.eat('&'); t = p.ident(); assert t == sub, (t, sub)
            inner = 'box(' + HDNAME.get(sub, sub) + ' ' + struct_body(p, sub) + ')'
            v = inner if kind == 'req' else '.Some(' + inner + ')'
        elif kind in ('list', 'optlist'):
            p.eat('[]*'); t = p.ident(); assert t == sub; p.eat('{'); xs = []
            while not p.peek('}'):
                xs.append('box(' + HDNAME.get(sub, sub) + ' ' + struct_body(p, sub) + ')')
                if p.peek(','): p.eat(',')
            p.eat('}'); v = '[' + ', '.join(xs) + ']'
            if kind == 'optlist': v = '.Some(' + v + ')'
        parts.append(name + ': ' + v)
        if p.peek(','): p.eat(',')
    p.eat('}')
    return '{ ' + ', '.join(parts) + ' }'

src = open(sys.argv[1]).read()
body = src[src.index('builtinFuncDefs = map[string][]*FuncDef{') + len('builtinFuncDefs = map[string][]*FuncDef{'):]
p = P(body); entries = []
while True:
    p.ws()
    if p.peek('}'): break
    key = p.gostring(); p.eat(':'); p.eat('{'); defs = []
    while not p.peek('}'):
        defs.append('box(FuncDef ' + struct_body(p, 'FuncDef') + ')')
        if p.peek(','): p.eat(',')
    p.eat('}'); p.eat(',')
    entries.append((key, defs))

out = ['## Port of gojq/builtin.go: the parsed function definitions of builtin.jq.',
       '## Generated by tools/gen_builtin.py from builtin.go; do not edit.',
       'use pkg.gojq.query.{Query, Term, TermType, Operator, FuncDef, Pattern, PatternObject, Index, Func, StringT, Object, ObjectKeyVal, Array, Suffix, If, IfElif, Try, Reduce, Foreach, Label, Unary}', '']
for i, (key, defs) in enumerate(entries):
    out.append(f'fn def_{i}() -> List[*mut FuncDef]:')
    out.append('    [' + ', '.join(defs) + ']')
    out.append('')
out.append('pub fn builtin_func_defs() -> Map[string, List[*mut FuncDef]]:')
out.append('    let mut m: Map[string, List[*mut FuncDef]] = {}')
for i, (key, defs) in enumerate(entries):
    out.append(f'    m[{hdstr(key)}] = def_{i}()')
out.append('    m')
open(sys.argv[2], 'w').write('\n'.join(out) + '\n')
print(len(entries), 'builtins')
