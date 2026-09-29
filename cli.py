"""English-first bilingual command-line help and argument errors."""
import argparse
import sys


class BilingualParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._positionals.title = 'Positional arguments / 位置参数'
        self._optionals.title = 'Options / 选项'

    def format_usage(self):
        return super().format_usage().replace('usage:', 'Usage / 用法:', 1)

    def format_help(self):
        return super().format_help().replace('usage:', 'Usage / 用法:', 1)

    def error(self, message):
        chinese = message.replace('unrecognized arguments:', '无法识别的参数：').replace('expected one argument', '需要一个参数').replace('argument ', '参数 ')
        if chinese == message:
            chinese = '命令行参数无效，请使用 --help 查看用法。'
        self.print_usage(sys.stderr)
        self.exit(2, f'Error: {message}\n错误：{chinese}\n')
