from matplotlib import font_manager as fm
from fontTools import ttLib

def init_font():
    for font in fm.fontManager.ttflist:
        if font.name == 'Helvetica':
            try:
                t = ttLib.TTFont(font.fname)
                t.getGlyphSet()  
                fm.fontManager.addfont(font.fname)
                return 'Helvetica'
            except Exception:
                continue  
    return 'Arial'

    
FONT = {
    'title':   10,
    'p-value': 7,
    'panel':   11,   
    'label':   8,
    'legend':  8,
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
    'font.sans-serif': ['Liberation Sans', 'DejaVu Sans'],
    'font.size': 11,
    'axes.linewidth': 0.6,
    'axes.labelsize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'xtick.major.size': 2.5,
    'ytick.major.size': 2.5,
    'legend.fontsize': 9,
    'legend.frameon': False,
    'pdf.fonttype': 3,
    'ps.fonttype': 3,
}