from app.schemas import ChatRequest, ChatResponse


def test_chat_request_e_resposta():
    requisicao = ChatRequest(token="  token  ", mensagem="  olá  ")
    resposta = ChatResponse(resposta="Olá")

    assert requisicao.token == "token"
    assert requisicao.mensagem == "olá"
    assert resposta.agentes_chamados == []
