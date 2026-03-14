from lib.annotation.import_files import *
import argparse
import lib.annotation.D_Annotation as da
import lib.annotation.tools.Q_Extract as qe
import lib.annotation.SampleSelf_Consistency_re as ssc


def main(ver):
    print ("start main!")
    ver = re.findall(r"\d+",ver)[0]
    print("start main! : ", ver)
    t_extract = qe.Q_Extract(ver)

    # while True :
    print("t_extract start")
    cnt = t_extract.chk_left()
    print(f"t_extract end_{cnt}")
    if cnt[0][0] > 0 : 
        print(f"Q_Extract start_{cnt[0][1]}")
        df = t_extract.db_extract()
        q_output = t_extract.tb_extract(df)
        print(f"Q_Extract end_{cnt[0][1]}")

        print(f"SampleSelf_Consistency start_{cnt[0][1]}")
        sample_sc = ssc.SampleSelf_Consistency_re(q_output) 
        print(f"SampleSelf_Consistency end_{cnt[0][1]}")
        
        print(f"get_annotation_data start_{cnt[0][1]}")
        sample_sc.get_annotation_data()
        print(f"get_annotation_data end_{cnt[0][1]}")

        print(f"random_selection start_{cnt[0][1]}")
        e_f_dict = sample_sc.random_selection()
        print(f"random_selection end_{cnt[0][1]}")

        print(f"write_promt start_{cnt[0][1]}")
        chk_list = sample_sc.write_prompt(e_f_dict)
        print(f"write_promt end_{cnt[0][1]}")

        print(f"calc_acc start_{cnt[0][1]}")
        result_df = sample_sc.calc_acc()
        print(f"calc_acc end_{cnt[0][1]}")
    else :
        print("Nothing left")





    

if __name__ == "__main__":
    # /home/mghan/sopjt/git/venv_stackoverflow_src/bin/python /home/mghan/sopjt/git/stackoverflow_src_2425/difficulty/automate_annotation/main.py ver150000  
    # /home/mghan/sopjt/git/stackoverflow_src/LLM/exec_d_a.sh ver150000 >> /home/mghan/sopjt/git/stackoverflow_src/LLM/log/log150000.log
    parser = argparse.ArgumentParser(description="이 프로그램은 파라미터를 처리합니다.")
    parser.add_argument("param1", type=str, help="")
    args = parser.parse_args()
    print(f"param1: {args.param1}")
    main(args.param1)

