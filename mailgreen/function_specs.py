FUNCTION_SPECS = [
    {
        "name": "mark_important",
        "description": "특정 조건의 메일을 중요 표시(별표)",
        "input_schema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string", "description": "메일의 발신자(이름 또는 이메일)", "nullable": True},
                "subject": {"type": "string", "description": "메일 제목(선택)", "nullable": True},
                "start_date": {"type": "string", "format": "date", "description": "조회 시작일(선택, YYYY-MM-DD)", "nullable": True},
                "end_date": {"type": "string", "format": "date", "description": "조회 종료일(선택, YYYY-MM-DD)", "nullable": True},
                "has_pdf": {"type": "boolean", "description": "PDF 첨부 여부(선택)", "nullable": True}
            }
        }
    },
    {
        "name": "read_mail",
        "description": "특정 조건의 메일을 읽음 처리",
        "input_schema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string", "description": "메일의 발신자(이름 또는 이메일)", "nullable": True},
                "subject": {"type": "string", "description": "메일 제목(선택)", "nullable": True},
                "start_date": {"type": "string", "format": "date", "description": "조회 시작일(선택, YYYY-MM-DD)", "nullable": True},
                "end_date": {"type": "string", "format": "date", "description": "조회 종료일(선택, YYYY-MM-DD)", "nullable": True},
                "has_pdf": {"type": "boolean", "description": "PDF 첨부 여부(선택)", "nullable": True}
            }
        }
    },
    {
        "name": "delete_mail",
        "description": "특정 조건의 메일을 삭제",
        "input_schema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string", "description": "메일의 발신자(이름 또는 이메일)", "nullable": True},
                "subject": {"type": "string", "description": "메일 제목(선택)", "nullable": True},
                "start_date": {"type": "string", "format": "date", "description": "조회 시작일(선택, YYYY-MM-DD)", "nullable": True},
                "end_date": {"type": "string", "format": "date", "description": "조회 종료일(선택, YYYY-MM-DD)", "nullable": True},
                "has_pdf": {"type": "boolean", "description": "PDF 첨부 여부(선택)", "nullable": True}
            }
        }
    },
    {
        "name": "search_mail",
        "description": "특정 조건의 메일을 조회",
        "input_schema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string", "description": "메일의 발신자(이름 또는 이메일)", "nullable": True},
                "subject": {"type": "string", "description": "메일 제목(선택)", "nullable": True},
                "start_date": {"type": "string", "format": "date", "description": "조회 시작일(선택, YYYY-MM-DD)", "nullable": True},
                "end_date": {"type": "string", "format": "date", "description": "조회 종료일(선택, YYYY-MM-DD)", "nullable": True},
                "is_read": {"type": "boolean", "description": "읽음 여부(선택)", "nullable": True},
                "has_pdf": {"type": "boolean", "description": "PDF 첨부 여부(선택)", "nullable": True}
            }
        }
    },
    {
        "name": "unsubscribe_mail",
        "description": "특정 조건의 메일에서 구독 해제(List-Unsubscribe 헤더 기반)",
        "input_schema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string", "description": "메일의 발신자(이름 또는 이메일)", "nullable": True},
                "subject": {"type": "string", "description": "메일 제목(선택)", "nullable": True},
                "start_date": {"type": "string", "format": "date", "description": "조회 시작일(선택, YYYY-MM-DD)", "nullable": True},
                "end_date": {"type": "string", "format": "date", "description": "조회 종료일(선택, YYYY-MM-DD)", "nullable": True}
            }
        }
    }
]