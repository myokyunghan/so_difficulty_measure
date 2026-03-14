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

    
font_setting = {'title' : 22,
                'p-value' : 15,
                'panel' : 25,
                'tick' : 15,
                'legend':15,
                'label':15
                }
