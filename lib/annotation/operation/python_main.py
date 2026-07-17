import re
import datetime as dt

from lib.utils.file_io import save_json
from lib.utils.file_io import create_dir

from lib.annotation.tools.loghander import *
from lib.annotation.tools.VLLM import VLLM
from lib.annotation.operation.annotation_operation import Annotation_Operation
import lib.annotation.tools.Q_Extract as qe

from setting_for_sdm.param import param
from run_project.annotate_difficulty.options import RunnerOptions


class ModelRunner:

    def __init__(self, runner_opt):
        self.runner_opt       = runner_opt
        self.operation_option = self.runner_opt.user_opt['operation_option']
        self.save_dir         = f"{self.runner_opt.user_opt['save_dir']}"
        init_logger(self.runner_opt.user_opt['log_dir'])

    def __call__(self):
        self.run()

    def run(self):
        create_dir(self.save_dir)
        self.run_annotation_iterative_full_target()
        self.save_option()

    def run_annotation_iterative_full_target(self):
        vllm = VLLM(self.operation_option['llm_model'], self.operation_option['model_ver'])
        
        while self.time_check(20) : 
            q_extract = qe.Q_Extract('python')
            cnt       = q_extract.chk_left_for_full_target()
            print(f'[Q_Extract] 남은 건수: {cnt[0][0]}, 기준 날짜: {cnt[0][1]}')

            if cnt[0][0] > 0:
                df       = q_extract.db_extract_for_full_target()
                q_output = q_extract.tb_extract(df)
                print(f'[Q_Extract] {len(q_output)}건 추출 완료')
                ap = Annotation_Operation(q_output, self.runner_opt.user_opt, vllm)
                ap()
            else:
                print('[ModelRunner] 어노테이션 대상 없음. 종료.')
                break

    def run_annotation_iterative(self):
        vllm = VLLM(self.operation_option['llm_model'], self.operation_option['model_ver'])
        
        while self.time_check(20) : 
            q_extract = qe.Q_Extract('python')
            cnt       = q_extract.chk_left()
            print(f'[Q_Extract] 남은 건수: {cnt[0][0]}, 기준 날짜: {cnt[0][1]}')

            if cnt[0][0] > 0:
                df       = q_extract.db_extract()
                q_output = q_extract.tb_extract(df)
                print(f'[Q_Extract] {len(q_output)}건 추출 완료')
                ap = Annotation_Operation(q_output, self.runner_opt.user_opt, vllm)
                ap()
            else:
                print('[ModelRunner] 어노테이션 대상 없음. 종료.')
                break

    def run_annotation(self):
        # ver는 숫자 문자열이어야 함 (e.g. '150000')
        # 'ver150000' 형태로 넘어온 경우를 방어적으로 처리
        ver = re.findall(r'\d+', str(self.ver))[0]
    
        q_extract = qe.Q_Extract(ver)
        cnt       = q_extract.chk_left()
        print(f'[Q_Extract] 남은 건수: {cnt[0][0]}, 기준 날짜: {cnt[0][1]}')

        if cnt[0][0] > 0:
            df       = q_extract.db_extract()
            q_output = q_extract.tb_extract(df)
            print(f'[Q_Extract] {len(q_output)}건 추출 완료')
            ap = Annotation_Operation(q_output, self.runner_opt.user_opt)
            ap()
        else:
            print('[ModelRunner] 어노테이션 대상 없음. 종료.')

    def save_option(self):
        save_json(self.runner_opt.user_opt, f'{self.save_dir}/option.json')
        print(f'[Saved] runner option → {self.save_dir}/option.json')


    
    def time_check(self, til_when):
        now = dt.datetime.now()
        return now.hour < til_when

if __name__ == "__main__":
    
    runner_opt = RunnerOptions(
        'operation',
        'python_1',
        param
    )

    runner = ModelRunner(runner_opt)
    runner()

    