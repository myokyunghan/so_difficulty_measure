from matplotlib import font_manager as fm

def init_font():
    for font in fm.fontManager.ttflist:
        if 'Helvetica' == font.name: 
            print(font.name, font.fname)
            font_path = font.fname
            break

    # 직접 경로로 Helvetica 폰트 불러오기
    font_prop = fm.FontProperties(fname=font_path)
    font_name = font_prop.get_name()
    print(f"Registered font name: {font_name}")
    return font_name

    
FONT = {'title' : 11,
        'p-value' : 11,
        'panel' : 25,
        'label':10.5,
        'legend' : 9.5
        }
PALETTE = {
    'primary': '#1f4e79',
    'accent':  '#E07A1F',
    'event':   '#C0392B',
    'neutral': '#555555',
    'point':   '#BBBBBB',
}

FIG_SIZE = {'x' : 2.4
           , 'y':2.6}

fig_setting = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9,
    'axes.linewidth': 0.8,
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'xtick.major.size': 3,
    'ytick.major.size': 3,
    'legend.fontsize': 8,
    'legend.frameon': False,
    'pdf.fonttype': 42,   
    'ps.fonttype': 42,
}